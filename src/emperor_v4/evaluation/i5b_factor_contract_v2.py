from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


TEST_SET_SCHEMA_VERSION = "i5b-factor-test-set-v2"
WORKLIST_SCHEMA_VERSION = "i5b-factor-worklist-v2"
RESPONSE_SCHEMA_VERSION = "i5b-factor-response-v2"
GOLD_SCHEMA_VERSION = "i5b-factor-gold-v2"
REPORT_SCHEMA_VERSION = "i5b-factor-qualification-report-v2"

APPLICABILITY_OPTIONS = frozenset(
    {"applicable", "not_applicable", "insufficient_evidence"}
)
APPLICABILITY_CASE_TO_STATUS = {
    "pollution_event": "applicable",
    "prevention_event": "applicable",
    "correction_event": "applicable",
    "outside_rule": "not_applicable",
    "unresolved": "insufficient_evidence",
}
QUALIFICATION_DATASET_ROLES = frozenset({"sealed_holdout"})
NON_QUALIFICATION_DATASET_ROLES = frozenset(
    {
        "open_development",
        "opened_regression",
        "opened_regression_only",
        "legacy_opened_regression",
    }
)
ALLOWED_DATASET_ROLES = QUALIFICATION_DATASET_ROLES | NON_QUALIFICATION_DATASET_ROLES
ALLOWED_CONTEXT_KINDS = frozenset(
    {"episode", "rule_evidence_unit", "aggregate_context", "ruler_time_window"}
)

# These fields can silently turn a categorical observation contract into scoring.
# Matching is case-insensitive and recursive.
FORBIDDEN_KEYS = frozenset(
    {
        "score",
        "scores",
        "raw_score",
        "ranking",
        "rank",
        "numeric_value",
        "numerical_value",
        "factor_value",
        "deterministic_value",
    }
)


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _assert_no_forbidden_keys(payload: object) -> None:
    if isinstance(payload, Mapping):
        found = {
            str(key)
            for key in payload
            if str(key).casefold() in FORBIDDEN_KEYS
            or str(key).casefold().endswith("_score")
        }
        if found:
            raise ValueError(f"第五项 v2 合同包含禁止的数值/score 字段: {sorted(found)}")
        for value in payload.values():
            _assert_no_forbidden_keys(value)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for value in payload:
            _assert_no_forbidden_keys(value)


def _unique_rows(rows: Sequence[Mapping[str, Any]], key: str, label: str) -> None:
    values = [row.get(key) for row in rows]
    if None in values or "" in values or len(values) != len(set(values)):
        raise ValueError(f"{label} 的 {key} 缺失或重复")


def _expected_applicability(applicability_case: object) -> str:
    try:
        return APPLICABILITY_CASE_TO_STATUS[str(applicability_case)]
    except KeyError as exc:
        raise ValueError(f"第五项 applicability_case 非法: {applicability_case}") from exc


def _case_mapping(payload: Mapping[str, Any]) -> dict[str, str]:
    mapping = payload.get("applicability_case_to_status")
    if mapping is None:
        mapping = APPLICABILITY_CASE_TO_STATUS
    if (
        not isinstance(mapping, Mapping)
        or not mapping
        or not set(mapping.values()) <= set(APPLICABILITY_OPTIONS)
    ):
        raise ValueError("第五项 v2 applicability_case_to_status 非法")
    return {str(case): str(status) for case, status in mapping.items()}


def _expected_applicability_from(
    payload: Mapping[str, Any], applicability_case: object
) -> str:
    mapping = _case_mapping(payload)
    try:
        return mapping[str(applicability_case)]
    except KeyError as exc:
        raise ValueError(f"第五项 applicability_case 非法: {applicability_case}") from exc


def _owned_factors(
    factor_ownership: Mapping[str, Any], context_kind: str
) -> tuple[str, ...]:
    factors = tuple(factor_ownership.get(context_kind) or ())
    if not factors:
        raise ValueError(f"context_kind={context_kind} 没有 owned factors")
    return tuple(sorted(str(name) for name in factors))


def validate_i5b_factor_test_set_v2(manifest: Mapping[str, Any]) -> None:
    """Validate a factor test-set manifest without reading or accepting Gold."""

    _assert_no_forbidden_keys(manifest)
    if manifest.get("schema_version") != TEST_SET_SCHEMA_VERSION:
        raise ValueError("第五项 v2 测试集 manifest 版本非法")
    for key in ("task_code", "rule_code", "factor_policy_version"):
        if not str(manifest.get(key) or "").strip():
            raise ValueError(f"第五项 v2 测试集缺少 {key}")
    dataset_role = manifest.get("dataset_role")
    if dataset_role not in ALLOWED_DATASET_ROLES:
        raise ValueError("第五项 v2 测试集 dataset_role 非法")
    if set(manifest.get("applicability_options") or APPLICABILITY_OPTIONS) != set(
        APPLICABILITY_OPTIONS
    ):
        raise ValueError("第五项 v2 applicability 值域非法")
    case_mapping = _case_mapping(manifest)
    if set(manifest.get("applicability_cases") or case_mapping) != set(case_mapping):
        raise ValueError("第五项 v2 applicability_case 值域非法")

    catalog = manifest.get("factor_option_catalog") or {}
    if not isinstance(catalog, Mapping) or not catalog:
        raise ValueError("第五项 v2 测试集缺少 factor_option_catalog")
    for factor_name, options in catalog.items():
        if not str(factor_name).strip() or not isinstance(options, Mapping):
            raise ValueError("第五项 v2 因子值域格式非法")
        if not {"not_applicable", "insufficient_evidence"} <= set(options):
            raise ValueError(f"{factor_name} 缺少安全退出 option")

    ownership = manifest.get("factor_ownership") or {}
    if not isinstance(ownership, Mapping) or not ownership:
        raise ValueError("第五项 v2 测试集缺少 factor_ownership")
    known_factors = set(catalog)
    owned_somewhere: set[str] = set()
    for context_kind, factors_value in ownership.items():
        if context_kind not in ALLOWED_CONTEXT_KINDS:
            raise ValueError(f"factor_ownership context_kind 非法: {context_kind}")
        factors = tuple(factors_value or ())
        if not factors or len(factors) != len(set(factors)):
            raise ValueError(f"{context_kind} owned factors 为空或重复")
        unknown = set(factors) - known_factors
        if unknown:
            raise ValueError(f"{context_kind} 声明未知 owned factors: {sorted(unknown)}")
        owned_somewhere.update(factors)
    if owned_somewhere != known_factors:
        missing = known_factors - owned_somewhere
        raise ValueError(f"存在无 context owner 的因子: {sorted(missing)}")

    units = tuple(manifest.get("units") or ())
    if not units:
        raise ValueError("第五项 v2 测试集缺少 units")
    expected_count = manifest.get("expected_unit_count")
    if expected_count is not None and expected_count != len(units):
        raise ValueError("第五项 v2 测试集单元数量不符合声明")
    _unique_rows(units, "unit_ref", "第五项 v2 units")
    for unit in units:
        unit_ref = unit["unit_ref"]
        context_kind = str(unit.get("context_kind") or "")
        _owned_factors(ownership, context_kind)
        evidence = tuple(unit.get("evidence") or ())
        if not evidence:
            raise ValueError(f"{unit_ref} 缺少 evidence")
        _unique_rows(evidence, "assertion_ref", f"{unit_ref} evidence")
        for row in evidence:
            if not str(row.get("summary") or "").strip():
                raise ValueError(f"{unit_ref} evidence summary 缺失")

    if dataset_role == "sealed_holdout":
        freeze = manifest.get("sealed_freeze") or {}
        if freeze.get("identity_and_gold_frozen_before_model") is not True:
            raise ValueError("sealed v2 测试集必须先冻结身份与 Gold")
        if freeze.get("allowed_model_runs") != 1:
            raise ValueError("sealed v2 测试集必须且只能授权一次模型运行")


def build_i5b_factor_worklist_v2(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build a Gold-blind worklist with explicit per-task factor ownership."""

    validate_i5b_factor_test_set_v2(manifest)
    ownership = manifest["factor_ownership"]
    tasks = []
    for unit in sorted(manifest["units"], key=lambda row: row["unit_ref"]):
        task = {
            key: unit[key]
            for key in (
                "unit_ref",
                "ruler",
                "subject",
                "person",
                "context_kind",
                "evaluation_window",
                "context_summary",
                "evidence",
                "profile_snapshots",
                "member_set",
                "coverage_tags",
                "structural_observations",
            )
            if key in unit
        }
        task["owned_factor_names"] = list(
            _owned_factors(ownership, str(unit["context_kind"]))
        )
        tasks.append(task)
    basis = {
        "rule_code": manifest["rule_code"],
        "dataset_role": manifest["dataset_role"],
        "effective_dataset_use": manifest.get(
            "effective_dataset_use", manifest["dataset_role"]
        ),
        "factor_policy_version": manifest["factor_policy_version"],
        "applicability_case_to_status": _case_mapping(manifest),
        "factor_option_catalog": manifest["factor_option_catalog"],
        "factor_ownership": manifest["factor_ownership"],
        "tasks": tasks,
    }
    return {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "status": "i5b_factor_worklist_v2_ready",
        "task_code": manifest["task_code"],
        "rule_code": manifest["rule_code"],
        "dataset_role": manifest["dataset_role"],
        "effective_dataset_use": manifest.get(
            "effective_dataset_use", manifest["dataset_role"]
        ),
        "factor_policy_version": manifest["factor_policy_version"],
        "input_boundary": {
            "gold_options_exposed": False,
            "numeric_values_exposed": False,
            "scores_or_rankings_exposed": False,
            "source_lineage_required": True,
        },
        "applicability_options": sorted(APPLICABILITY_OPTIONS),
        "applicability_case_to_status": _case_mapping(manifest),
        "factor_option_catalog": manifest["factor_option_catalog"],
        "factor_ownership": manifest["factor_ownership"],
        "output_contract": {
            "response_schema_version": RESPONSE_SCHEMA_VERSION,
            "factor_fields": ["option_code", "reason", "assertion_refs"],
            "factors_must_exactly_match_owned_factor_names": True,
            "forbidden_keys": sorted(FORBIDDEN_KEYS),
        },
        "tasks": tasks,
        "worklist_sha256": _stable_hash(basis),
    }


def _worklist_basis(worklist: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_code": worklist.get("rule_code"),
        "dataset_role": worklist.get("dataset_role"),
        "effective_dataset_use": worklist.get("effective_dataset_use"),
        "factor_policy_version": worklist.get("factor_policy_version"),
        "applicability_case_to_status": worklist.get(
            "applicability_case_to_status"
        ),
        "factor_option_catalog": worklist.get("factor_option_catalog"),
        "factor_ownership": worklist.get("factor_ownership"),
        "tasks": worklist.get("tasks"),
    }


def _validate_worklist_v2(worklist: Mapping[str, Any]) -> None:
    _assert_no_forbidden_keys(worklist)
    if (
        worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION
        or worklist.get("status") != "i5b_factor_worklist_v2_ready"
        or worklist.get("worklist_sha256") != _stable_hash(_worklist_basis(worklist))
    ):
        raise ValueError("第五项 v2 worklist 身份非法")
    tasks = tuple(worklist.get("tasks") or ())
    _unique_rows(tasks, "unit_ref", "第五项 v2 worklist tasks")
    catalog = worklist.get("factor_option_catalog") or {}
    ownership = worklist.get("factor_ownership") or {}
    for task in tasks:
        wanted = _owned_factors(ownership, str(task.get("context_kind") or ""))
        if tuple(task.get("owned_factor_names") or ()) != wanted:
            raise ValueError(f"{task['unit_ref']} owned_factor_names 与 context owner 不一致")
        if not set(wanted) <= set(catalog):
            raise ValueError(f"{task['unit_ref']} owned factors 不在 catalog")


def validate_i5b_factor_response_v2(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> None:
    _validate_worklist_v2(worklist)
    _assert_no_forbidden_keys(response)
    identity = (
        ("schema_version", RESPONSE_SCHEMA_VERSION),
        ("status", "i5b_factor_response_v2_complete"),
        ("worklist_sha256", worklist.get("worklist_sha256")),
        ("rule_code", worklist.get("rule_code")),
        ("dataset_role", worklist.get("dataset_role")),
        ("factor_policy_version", worklist.get("factor_policy_version")),
    )
    if any(response.get(key) != wanted for key, wanted in identity):
        raise ValueError("第五项 v2 response 版本或 worklist 身份非法")
    expected = {row["unit_ref"]: row for row in worklist.get("tasks") or ()}
    results = tuple(response.get("results") or ())
    _unique_rows(results, "unit_ref", "第五项 v2 response results")
    if {row["unit_ref"] for row in results} != set(expected):
        raise ValueError("第五项 v2 response 未完整唯一覆盖 worklist")
    catalog = worklist["factor_option_catalog"]
    for result in results:
        unit_ref = result["unit_ref"]
        applicability = result.get("applicability")
        expected_status = _expected_applicability_from(
            worklist, result.get("applicability_case")
        )
        if applicability != expected_status:
            raise ValueError(f"{unit_ref} applicability_case 与 applicability 不一致")
        factors = result.get("factors") or {}
        owned = set(expected[unit_ref]["owned_factor_names"])
        if set(factors) != owned:
            raise ValueError(f"{unit_ref} response 必须精确覆盖 owned factors")
        allowed_refs = {
            row["assertion_ref"] for row in expected[unit_ref].get("evidence") or ()
        }
        terminal = None if applicability == "applicable" else applicability
        for factor_name, factor in factors.items():
            if set(factor) != {"option_code", "reason", "assertion_refs"}:
                raise ValueError(f"{unit_ref}/{factor_name} response 字段非法")
            option_code = factor.get("option_code")
            if option_code not in catalog[factor_name]:
                raise ValueError(f"{unit_ref}/{factor_name} option_code 非法")
            if terminal and option_code != terminal:
                raise ValueError(f"{unit_ref}/{factor_name} 未使用一致的退出 option")
            if applicability == "applicable" and option_code in {
                "not_applicable",
                "insufficient_evidence",
            }:
                raise ValueError(f"{unit_ref}/{factor_name} applicable 不得使用退出 option")
            refs = tuple(factor.get("assertion_refs") or ())
            if (
                not str(factor.get("reason") or "").strip()
                or not refs
                or len(refs) != len(set(refs))
                or not set(refs) <= allowed_refs
            ):
                raise ValueError(f"{unit_ref}/{factor_name} reason 或 assertion_refs 非法")


def validate_i5b_factor_gold_v2(
    worklist: Mapping[str, Any], gold: Mapping[str, Any]
) -> None:
    """Validate categorical Gold and its evidence support against worklist inputs."""

    _validate_worklist_v2(worklist)
    _assert_no_forbidden_keys(gold)
    identity = (
        ("schema_version", GOLD_SCHEMA_VERSION),
        ("worklist_sha256", worklist.get("worklist_sha256")),
        ("rule_code", worklist.get("rule_code")),
        ("dataset_role", worklist.get("dataset_role")),
        ("factor_policy_version", worklist.get("factor_policy_version")),
    )
    if any(gold.get(key) != wanted for key, wanted in identity):
        raise ValueError("第五项 v2 Gold 版本或 worklist 身份非法")
    expected = {row["unit_ref"]: row for row in worklist.get("tasks") or ()}
    units = tuple(gold.get("units") or ())
    _unique_rows(units, "unit_ref", "第五项 v2 Gold units")
    if {row["unit_ref"] for row in units} != set(expected):
        raise ValueError("第五项 v2 Gold 未完整唯一覆盖 worklist")
    catalog = worklist["factor_option_catalog"]
    for unit in units:
        unit_ref = unit["unit_ref"]
        applicability = unit.get("applicability")
        if applicability != _expected_applicability_from(
            worklist, unit.get("applicability_case")
        ):
            raise ValueError(f"{unit_ref} Gold applicability_case 与 applicability 不一致")
        factors = unit.get("factors") or {}
        owned = set(expected[unit_ref]["owned_factor_names"])
        if set(factors) != owned:
            raise ValueError(f"{unit_ref} Gold 必须精确覆盖 owned factors")
        allowed_refs = {
            row["assertion_ref"] for row in expected[unit_ref].get("evidence") or ()
        }
        terminal = None if applicability == "applicable" else applicability
        for factor_name, factor in factors.items():
            if set(factor) != {"option_code", "assertion_refs"}:
                raise ValueError(f"{unit_ref}/{factor_name} Gold 必须为 option_code+assertion_refs")
            option_code = factor.get("option_code")
            if option_code not in catalog[factor_name]:
                raise ValueError(f"{unit_ref}/{factor_name} Gold option_code 非法")
            if terminal and option_code != terminal:
                raise ValueError(f"{unit_ref}/{factor_name} Gold 退出 option 不一致")
            if applicability == "applicable" and option_code in {
                "not_applicable",
                "insufficient_evidence",
            }:
                raise ValueError(f"{unit_ref}/{factor_name} Gold applicable 使用了退出 option")
            refs = tuple(factor.get("assertion_refs") or ())
            if not refs or len(refs) != len(set(refs)) or not set(refs) <= allowed_refs:
                raise ValueError(f"{unit_ref}/{factor_name} Gold assertion_refs 不受输入支持")


def evaluate_i5b_factor_qualification_v2(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    gold: Mapping[str, Any],
    *,
    minimum_factor_exact_rate: float = 0.85,
) -> dict[str, Any]:
    """Compare owned factors only; opened/legacy datasets never assert qualification."""

    validate_i5b_factor_response_v2(worklist, response)
    validate_i5b_factor_gold_v2(worklist, gold)
    if not 0.0 <= minimum_factor_exact_rate <= 1.0:
        raise ValueError("minimum_factor_exact_rate 必须在 0 到 1 之间")
    expected = {row["unit_ref"]: row for row in gold["units"]}
    actual = {row["unit_ref"]: row for row in response["results"]}
    tasks = {row["unit_ref"]: row for row in worklist["tasks"]}
    applicability_correct = 0
    factor_correct = 0
    owned_factor_denominator = 0
    unsafe_false_applicable = 0
    mismatches = []
    breakdown: dict[str, Counter[str]] = {
        name: Counter() for name in worklist["factor_option_catalog"]
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
        for factor_name in tasks[unit_ref]["owned_factor_names"]:
            owned_factor_denominator += 1
            wanted_option = wanted["factors"][factor_name]["option_code"]
            observed_option = observed["factors"][factor_name]["option_code"]
            matched = wanted_option == observed_option
            breakdown[factor_name]["correct" if matched else "incorrect"] += 1
            factor_correct += int(matched)
            if not matched:
                mismatches.append(
                    {
                        "unit_ref": unit_ref,
                        "field": factor_name,
                        "expected": wanted_option,
                        "actual": observed_option,
                    }
                )
    unit_count = len(expected)
    applicability_rate = applicability_correct / unit_count
    factor_rate = factor_correct / owned_factor_denominator
    role = worklist["dataset_role"]
    effective_use = worklist.get("effective_dataset_use", role)
    qualification_claim_allowed = (
        role in QUALIFICATION_DATASET_ROLES
        and effective_use not in NON_QUALIFICATION_DATASET_ROLES
    )
    gate_passed = (
        applicability_rate == 1.0
        and factor_rate >= minimum_factor_exact_rate
        and unsafe_false_applicable == 0
    )
    summary: dict[str, Any] = {
        "unit_count": unit_count,
        "applicability_exact_count": applicability_correct,
        "applicability_exact_rate": applicability_rate,
        "owned_factor_comparison_count": owned_factor_denominator,
        "owned_factor_exact_count": factor_correct,
        "owned_factor_exact_rate": factor_rate,
        "unsafe_false_applicable_count": unsafe_false_applicable,
        "qualification_claim_allowed": qualification_claim_allowed,
    }
    if qualification_claim_allowed:
        summary["qualification_gate_passed"] = gate_passed
    else:
        summary["regression_gate_passed"] = gate_passed
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": (
            "i5b_factor_qualification_evaluated"
            if qualification_claim_allowed
            else "i5b_opened_regression_evaluated"
        ),
        "rule_code": worklist["rule_code"],
        "dataset_role": role,
        "factor_policy_version": worklist["factor_policy_version"],
        "worklist_sha256": worklist["worklist_sha256"],
        "summary": summary,
        "factor_breakdown": {
            name: {
                "correct": counts["correct"],
                "incorrect": counts["incorrect"],
                "exact_rate": (
                    counts["correct"] / sum(counts.values())
                    if sum(counts.values())
                    else None
                ),
            }
            for name, counts in breakdown.items()
            if sum(counts.values())
        },
        "mismatches": mismatches,
        "qualification_claim_allowed": qualification_claim_allowed,
        "formal_scoring_allowed": False,
        "database_write_count": 0,
    }


# Short aliases keep call sites readable while the schema version remains explicit.
validate_i5b_factor_manifest_v2 = validate_i5b_factor_test_set_v2
validate_i5b_factor_test_set = validate_i5b_factor_test_set_v2
build_i5b_factor_worklist = build_i5b_factor_worklist_v2
validate_i5b_factor_response = validate_i5b_factor_response_v2
validate_i5b_factor_gold = validate_i5b_factor_gold_v2
evaluate_i5b_factor_qualification = evaluate_i5b_factor_qualification_v2
