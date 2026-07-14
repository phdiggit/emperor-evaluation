from __future__ import annotations

from collections import Counter
from copy import deepcopy
from math import ceil
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash
from emperor_v4.evaluation.appointment_delegation_v3_parity import (
    FACTOR_NAMES,
    FACTOR_SCHEMA_VERSION,
    JUDGMENT_POLICY_VERSION,
    RULE_CODE,
    SCORING_FORMULA_VERSION,
    observation_fingerprint,
    validate_parity_manifest,
)


WORKLIST_SCHEMA_VERSION = "factor-observation-worklist-v1"
RESPONSE_SCHEMA_VERSION = "factor-observation-agent-response-v1"
QUALIFICATION_SCHEMA_VERSION = "factor-observation-qualification-v1"
BATCH_PLAN_SCHEMA_VERSION = "factor-observation-batch-plan-v1"
AGENT_POLICY_VERSION = "appointment-delegation-factor-observation-agent-v1"

OPTION_GUIDANCE: dict[str, dict[str, str]] = {
    "appointment_importance": {
        "nominal_or_light": "名义任用、轻量职责或影响范围很小",
        "real_bounded": "真实职责成立，但责任域明确且有限",
        "major_affairs": "重要军政事务或方面职责",
        "critical_national_or_long_term": "国家级关键职责或长期结构性授权",
    },
    "appointment_effect": {
        "major_success": "授权后产生可归责的重大成功",
        "normal_success": "履职和反馈明确，达到正常成功",
        "weak_feedback": "存在正向反馈，但结果较弱或不完整",
        "poor_result": "授权控制或履职结果较差",
        "major_direct_damage": "授权直接造成重大损害",
        "structural_continuing_damage": "形成持续性的结构损害",
    },
    "continuity_factor": {
        "short_or_one_off": "单次或短期授权，缺少跨阶段复用",
        "stable": "存在稳定履职或持续反馈",
        "long_term_multi_stage": "跨多个阶段持续授权和复用",
    },
    "attribution_factor": {
        "indirect": "皇帝责任成立但受他人行为或复杂链条显著影响",
        "direct": "任命、授权或反馈处置可直接归责于皇帝",
        "direct_under_pressure": "皇帝在压力或反对意见下直接作出关键取舍",
    },
    "source_factor": {
        "weak_or_compressed": "史源链压缩、间接或关键环节较弱",
        "standard": "史源足以支持本材料的主要判断",
        "complete_direct_chain": "史源直接覆盖任用、职责和结果链",
    },
    "context_factor": {
        "weak_but_applicable": "与规则相关，但上下文较弱或边界不完整",
        "clear": "规则上下文和结算边界清楚",
        "core_mechanism_direct": "直接展示任用、授权、反馈的核心机制",
    },
}

OPTION_ORDER: dict[str, tuple[str, ...]] = {
    "appointment_importance": (
        "nominal_or_light",
        "real_bounded",
        "major_affairs",
        "critical_national_or_long_term",
    ),
    "appointment_effect": (
        "structural_continuing_damage",
        "major_direct_damage",
        "poor_result",
        "weak_feedback",
        "normal_success",
        "major_success",
    ),
    "continuity_factor": ("short_or_one_off", "stable", "long_term_multi_stage"),
    "attribution_factor": ("indirect", "direct", "direct_under_pressure"),
    "source_factor": ("weak_or_compressed", "standard", "complete_direct_chain"),
    "context_factor": ("weak_but_applicable", "clear", "core_mechanism_direct"),
}

POSITIVE_EFFECT_OPTIONS = frozenset({"major_success", "normal_success", "weak_feedback"})
NEGATIVE_EFFECT_OPTIONS = frozenset(
    {"poor_result", "major_direct_damage", "structural_continuing_damage"}
)
FORBIDDEN_RESPONSE_KEYS = frozenset(
    {
        "score",
        "raw_score",
        "value_num",
        "numeric_value",
        "deterministic_value",
        "factor_value",
        "ranking",
    }
)


def _assertion_lineage_for_unit(
    unit: Mapping[str, Any],
    episode_by_ref: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    return {
        str(assertion_ref)
        for episode_ref in unit.get("episode_refs") or ()
        for assertion_ref in (episode_by_ref.get(str(episode_ref)) or {}).get(
            "assertion_refs", ()
        )
    }


def build_factor_observation_worklist(
    source_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if source_manifest.get("rule_code") != RULE_CODE:
        raise ValueError("Factor Observation worklist source rule_code 非法")

    assertions = {
        str(row["assertion_ref"]): row for row in source_manifest.get("assertions") or ()
    }
    episodes = {
        str(row["episode_ref"]): row
        for row in source_manifest.get("historical_episodes") or ()
    }
    passages = {
        str(row["passage_ref"]): row
        for row in source_manifest.get("source_passages") or ()
    }
    units = tuple(source_manifest.get("rule_evidence_units") or ())
    if not units:
        raise ValueError("Factor Observation worklist 缺少 RuleEvidenceUnit")

    tasks = []
    for unit in units:
        unit_ref = str(unit.get("unit_ref") or "")
        lineage = _assertion_lineage_for_unit(unit, episodes)
        if not unit_ref or not lineage or not lineage <= set(assertions):
            raise ValueError(f"{unit_ref or '<missing>'} Assertion lineage 不完整")
        task_assertions = []
        for assertion_ref in sorted(lineage):
            assertion = assertions[assertion_ref]
            passage = passages.get(str(assertion.get("source_passage_ref"))) or {}
            task_assertions.append(
                {
                    "assertion_ref": assertion_ref,
                    "summary": assertion["summary"],
                    "source": {
                        "passage_ref": assertion["source_passage_ref"],
                        "source_title": passage.get("source_title"),
                        "locator": passage.get("locator"),
                        "url": passage.get("url"),
                    },
                }
            )
        task_episodes = [
            {
                key: episode[key]
                for key in (
                    "episode_ref",
                    "episode_code",
                    "action",
                    "responsibility",
                    "outcome",
                    "assertion_refs",
                )
            }
            for episode_ref in unit["episode_refs"]
            for episode in (episodes[str(episode_ref)],)
        ]
        tasks.append(
            {
                "unit_ref": unit_ref,
                "source_observation_fingerprint": observation_fingerprint(unit),
                "ruler": unit["ruler"],
                "person": unit["person"],
                "decision_arc_family": unit["decision_arc_family"],
                "episodes": task_episodes,
                "assertions": task_assertions,
                "prior_v4_judge_observations": deepcopy(unit["factor_observations"]),
            }
        )

    semantic = {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "rule_code": RULE_CODE,
        "factor_schema_version": FACTOR_SCHEMA_VERSION,
        "agent_policy_version": AGENT_POLICY_VERSION,
        "tasks": tasks,
        "factor_option_catalog": OPTION_GUIDANCE,
    }
    worklist_hash = canonical_hash(semantic)
    return {
        **semantic,
        "status": "factor_observation_blind_worklist_ready",
        "task_code": "V4-AD-FACTOR-OBSERVATION-QUALIFICATION",
        "worklist_sha256": worklist_hash,
        "input_boundary": {
            "uses_v4_judge_observations": True,
            "uses_assertion_lineage": True,
            "v3_factor_gold_exposed": False,
            "numeric_factor_values_exposed": False,
            "scores_or_rankings_exposed": False,
        },
        "output_contract": {
            "response_schema_version": RESPONSE_SCHEMA_VERSION,
            "required_result_fields": ["unit_ref", "factor_materials"],
            "factor_material_fields": ["material_code", "event_group", "side", "factors"],
            "factor_fields": ["option_code", "reason", "assertion_refs"],
            "forbidden_keys": sorted(FORBIDDEN_RESPONSE_KEYS),
        },
    }


def _worklist_semantic_payload(worklist: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(worklist[key])
        for key in (
            "schema_version",
            "rule_code",
            "factor_schema_version",
            "agent_policy_version",
            "tasks",
            "factor_option_catalog",
        )
    }


def build_factor_observation_batch_plan(
    source_manifest: Mapping[str, Any],
    *,
    max_units_per_batch: int = 4,
    max_workers: int = 4,
) -> dict[str, Any]:
    """按稳定输入顺序建立可并发的受控微批计划，不执行模型调用。"""

    if max_units_per_batch <= 0 or max_workers <= 0:
        raise ValueError("Factor Observation 批大小和并发数必须为正整数")
    source_worklist = build_factor_observation_worklist(source_manifest)
    tasks = tuple(source_worklist["tasks"])
    batches = []
    for index, start in enumerate(range(0, len(tasks), max_units_per_batch), start=1):
        batch = deepcopy(source_worklist)
        batch["tasks"] = deepcopy(tasks[start : start + max_units_per_batch])
        batch["task_code"] = f"{source_worklist['task_code']}-B{index:03d}"
        batch["worklist_sha256"] = canonical_hash(_worklist_semantic_payload(batch))
        batches.append(
            {
                "batch_index": index,
                "unit_refs": [task["unit_ref"] for task in batch["tasks"]],
                "worklist": batch,
            }
        )

    effective_workers = min(max_workers, len(batches))
    return {
        "schema_version": BATCH_PLAN_SCHEMA_VERSION,
        "status": "factor_observation_batch_plan_ready",
        "task_code": "V4-AD-FACTOR-OBSERVATION-BATCH-PLAN",
        "source_worklist_sha256": source_worklist["worklist_sha256"],
        "scheduling_policy": {
            "optimization_objective": "wall_clock_latency_first",
            "max_units_per_batch": max_units_per_batch,
            "requested_max_workers": max_workers,
            "effective_max_workers": effective_workers,
            "batch_count": len(batches),
            "estimated_parallel_waves": ceil(len(batches) / effective_workers),
            "token_accounting_required": True,
            "quality_gate_required": True,
        },
        "batches": batches,
        "side_effect_audit": {
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
    }


def merge_factor_observation_batch_responses(
    batch_plan: Mapping[str, Any],
    responses: Sequence[Mapping[str, Any]],
    source_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """校验每个微批并按原始稳定顺序合并，供既有资格门消费。"""

    if (
        batch_plan.get("schema_version") != BATCH_PLAN_SCHEMA_VERSION
        or batch_plan.get("status") != "factor_observation_batch_plan_ready"
    ):
        raise ValueError("Factor Observation batch plan 合同非法")
    batches = tuple(batch_plan.get("batches") or ())
    if not batches or len(responses) != len(batches):
        raise ValueError("Factor Observation batch response 未完整覆盖批计划")

    merged_results = []
    shared_metadata = None
    for batch, response in zip(batches, responses, strict=True):
        worklist = batch.get("worklist") or {}
        unit_refs = set(batch.get("unit_refs") or ())
        if unit_refs != {task["unit_ref"] for task in worklist.get("tasks") or ()}:
            raise ValueError("Factor Observation batch unit_refs 与 worklist 不一致")
        sliced_source = deepcopy(source_manifest)
        sliced_source["rule_evidence_units"] = [
            unit
            for unit in source_manifest.get("rule_evidence_units") or ()
            if unit.get("unit_ref") in unit_refs
        ]
        validate_factor_observation_response(worklist, response, sliced_source)
        metadata = {
            key: deepcopy(response[key])
            for key in (
                "schema_version",
                "status",
                "agent_policy_version",
                "response_origin",
                "provider",
                "model",
                "blind_run_declarations",
            )
        }
        if shared_metadata is None:
            shared_metadata = metadata
        elif metadata != shared_metadata:
            raise ValueError("Factor Observation batch response 执行身份不一致")
        merged_results.extend(deepcopy(response["results"]))

    source_worklist = build_factor_observation_worklist(source_manifest)
    if source_worklist["worklist_sha256"] != batch_plan.get(
        "source_worklist_sha256"
    ):
        raise ValueError("Factor Observation batch plan 已相对源 worklist 失效")
    merged = {
        **(shared_metadata or {}),
        "worklist_sha256": source_worklist["worklist_sha256"],
        "results": merged_results,
    }
    validate_factor_observation_response(source_worklist, merged, source_manifest)
    return merged


def _find_forbidden_keys(value: Any, path: str = "$ response") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in FORBIDDEN_RESPONSE_KEYS:
                found.append(child_path)
            found.extend(_find_forbidden_keys(child, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_keys(child, f"{path}[{index}]"))
    return found


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], label: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} 字段必须严格匹配输出 Schema")


def validate_factor_observation_response(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> None:
    _require_exact_keys(
        response,
        {
            "schema_version",
            "status",
            "worklist_sha256",
            "agent_policy_version",
            "response_origin",
            "provider",
            "model",
            "blind_run_declarations",
            "results",
        },
        "Factor Observation response",
    )
    if (
        worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION
        or worklist.get("status") != "factor_observation_blind_worklist_ready"
        or response.get("schema_version") != RESPONSE_SCHEMA_VERSION
        or response.get("status") != "factor_observation_agent_response_complete"
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("agent_policy_version") != AGENT_POLICY_VERSION
    ):
        raise ValueError("Factor Observation response 版本、状态或 worklist 绑定非法")
    origin = response.get("response_origin")
    expected_gold_access = origin == "contract_fixture_from_human_calibration"
    declarations = response.get("blind_run_declarations") or {}
    if declarations != {
        "v3_factor_gold_accessed": expected_gold_access,
        "old_factor_proposals_accessed": expected_gold_access,
        "numeric_factor_values_supplied": False,
        "scoring_performed": False,
        "database_write_count": 0,
        "formal_acceptance_performed": False,
    }:
        raise ValueError("Factor Observation response 盲评与副作用声明非法")
    if origin not in {
        "contract_fixture_from_human_calibration",
        "independent_blind_agent_run",
        "development_replay_after_gold_opened",
    }:
        raise ValueError("Factor Observation response_origin 非法")
    if not str(response.get("provider") or "").strip() or not str(
        response.get("model") or ""
    ).strip():
        raise ValueError("Factor Observation response 缺少 provider 或 model")
    forbidden = _find_forbidden_keys(response.get("results") or ())
    if forbidden:
        raise ValueError(f"Factor Observation response 不得携带数值或排名字段: {forbidden[0]}")

    tasks = tuple(worklist.get("tasks") or ())
    task_by_ref = {str(row.get("unit_ref")): row for row in tasks}
    results = tuple(response.get("results") or ())
    result_by_ref = {str(row.get("unit_ref")): row for row in results}
    if (
        "None" in result_by_ref
        or len(result_by_ref) != len(results)
        or set(result_by_ref) != set(task_by_ref)
    ):
        raise ValueError("Factor Observation response 必须完整且唯一覆盖 worklist")
    for result in results:
        _require_exact_keys(
            result,
            {"unit_ref", "factor_materials"},
            f"{result.get('unit_ref')} result",
        )
        for material in result.get("factor_materials") or ():
            _require_exact_keys(
                material,
                {"material_code", "event_group", "side", "factors"},
                f"{material.get('material_code')} factor_material",
            )
            for factor_name, factor in (material.get("factors") or {}).items():
                _require_exact_keys(
                    factor,
                    {"option_code", "reason", "assertion_refs"},
                    f"{material.get('material_code')}.{factor_name}",
                )

    synthetic_manifest = {
        "schema_version": 1,
        "status": "frozen_v3_parity_shadow_input",
        "rule_code": RULE_CODE,
        "factor_schema_version": FACTOR_SCHEMA_VERSION,
        "judgment_policy_version": JUDGMENT_POLICY_VERSION,
        "scoring_formula_version": SCORING_FORMULA_VERSION,
        "runtime_policy": {
            "mode": "offline_report_only_shadow",
            "model_calls_allowed": False,
            "database_writes_allowed": False,
            "formal_acceptance_allowed": False,
        },
        "factor_judgment_proposals": [
            {
                **deepcopy(result),
                "proposal_status": "agent_proposed_shadow",
                "review_basis": "blind_factor_observation_worklist",
                "reviewer": f"{response['provider']}:{response['model']}",
                "source_observation_fingerprint": task_by_ref[unit_ref][
                    "source_observation_fingerprint"
                ],
            }
            for unit_ref, result in result_by_ref.items()
        ],
    }
    validate_parity_manifest(
        synthetic_manifest,
        source_manifest,
        allowed_proposal_statuses=frozenset({"agent_proposed_shadow"}),
        allowed_review_bases=frozenset({"blind_factor_observation_worklist"}),
    )
    for result in results:
        for material in result["factor_materials"]:
            effect = material["factors"]["appointment_effect"]["option_code"]
            if material["side"] == "positive" and effect not in POSITIVE_EFFECT_OPTIONS:
                raise ValueError(f"{material['material_code']} side 与 effect 方向冲突")
            if material["side"] == "negative" and effect not in NEGATIVE_EFFECT_OPTIONS:
                raise ValueError(f"{material['material_code']} side 与 effect 方向冲突")


def evaluate_factor_observation_qualification(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    gold_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    validate_factor_observation_response(worklist, response, source_manifest)
    validate_parity_manifest(gold_manifest, source_manifest)

    gold_by_unit = {
        row["unit_ref"]: row for row in gold_manifest["factor_judgment_proposals"]
    }
    response_by_unit = {row["unit_ref"]: row for row in response["results"]}
    exact = adjacent = nonadjacent = direction_errors = 0
    factor_total = 0
    structure_exact_units = 0
    factor_classifications = {name: Counter() for name in FACTOR_NAMES}
    unit_results = []
    for task in worklist["tasks"]:
        unit_ref = task["unit_ref"]
        candidate_materials = response_by_unit[unit_ref]["factor_materials"]
        gold_materials = gold_by_unit[unit_ref]["factor_materials"]
        candidate_side_counts = Counter(row["side"] for row in candidate_materials)
        gold_side_counts = Counter(row["side"] for row in gold_materials)
        structure_exact = candidate_side_counts == gold_side_counts
        if structure_exact:
            structure_exact_units += 1
        comparisons = []
        if structure_exact:
            material_pairs = []
            for side in sorted(gold_side_counts):
                candidate_side = sorted(
                    (row for row in candidate_materials if row["side"] == side),
                    key=lambda row: row["event_group"],
                )
                gold_side = sorted(
                    (row for row in gold_materials if row["side"] == side),
                    key=lambda row: row["event_group"],
                )
                material_pairs.extend(zip(candidate_side, gold_side))
            for candidate, gold in material_pairs:
                for factor_name in FACTOR_NAMES:
                    factor_total += 1
                    candidate_code = candidate["factors"][factor_name]["option_code"]
                    gold_code = gold["factors"][factor_name]["option_code"]
                    distance = abs(
                        OPTION_ORDER[factor_name].index(candidate_code)
                        - OPTION_ORDER[factor_name].index(gold_code)
                    )
                    if candidate_code == gold_code:
                        classification = "exact"
                        exact += 1
                    elif factor_name == "appointment_effect" and (
                        (candidate_code in POSITIVE_EFFECT_OPTIONS)
                        != (gold_code in POSITIVE_EFFECT_OPTIONS)
                    ):
                        classification = "direction_error"
                        direction_errors += 1
                    elif distance == 1:
                        classification = "adjacent"
                        adjacent += 1
                    else:
                        classification = "nonadjacent"
                        nonadjacent += 1
                    factor_classifications[factor_name][classification] += 1
                    comparisons.append(
                        {
                            "candidate_event_group": candidate["event_group"],
                            "gold_event_group": gold["event_group"],
                            "side": candidate["side"],
                            "factor_name": factor_name,
                            "candidate_option": candidate_code,
                            "gold_option": gold_code,
                            "classification": classification,
                        }
                    )
        unit_results.append(
            {
                "unit_ref": unit_ref,
                "material_side_structure_exact": structure_exact,
                "factor_comparisons": comparisons,
            }
        )

    unit_count = len(worklist["tasks"])
    exact_rate = exact / factor_total if factor_total else 0.0
    structure_rate = structure_exact_units / unit_count if unit_count else 0.0
    thresholds = {
        "factor_exact_match_rate_min": 0.85,
        "material_side_structure_exact_rate_min": 1.0,
        "direction_error_max": 0,
        "nonadjacent_error_max": 0,
        "contract_validation_required": True,
    }
    threshold_checks = {
        "factor_exact_match_rate": exact_rate >= thresholds["factor_exact_match_rate_min"],
        "material_side_structure_exact_rate": structure_rate
        >= thresholds["material_side_structure_exact_rate_min"],
        "direction_error": direction_errors <= thresholds["direction_error_max"],
        "nonadjacent_error": nonadjacent <= thresholds["nonadjacent_error_max"],
        "contract_validation": True,
    }
    threshold_passed = all(threshold_checks.values())
    independent = response["response_origin"] == "independent_blind_agent_run"
    contract_fixture = (
        response["response_origin"] == "contract_fixture_from_human_calibration"
    )
    development_replay = (
        response["response_origin"] == "development_replay_after_gold_opened"
    )
    real_agent_qualified = independent and threshold_passed
    factor_breakdown = {
        factor_name: {
            "comparison_count": sum(counts.values()),
            "exact_count": counts["exact"],
            "exact_rate": round(
                counts["exact"] / sum(counts.values()) if counts else 0.0,
                4,
            ),
            "adjacent_error_count": counts["adjacent"],
            "nonadjacent_error_count": counts["nonadjacent"],
            "direction_error_count": counts["direction_error"],
        }
        for factor_name, counts in factor_classifications.items()
    }
    report = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "status": (
            "factor_observation_agent_qualified"
            if real_agent_qualified
            else "factor_observation_development_replay_completed"
            if development_replay
            else "factor_observation_qualification_harness_ready"
            if not independent and threshold_passed
            else "factor_observation_agent_not_qualified"
        ),
        "rule_code": RULE_CODE,
        "worklist_sha256": worklist["worklist_sha256"],
        "response_origin": response["response_origin"],
        "provider": response["provider"],
        "model": response["model"],
        "metrics": {
            "unit_count": unit_count,
            "factor_comparison_count": factor_total,
            "factor_exact_match_count": exact,
            "factor_exact_match_rate": round(exact_rate, 4),
            "adjacent_error_count": adjacent,
            "nonadjacent_error_count": nonadjacent,
            "direction_error_count": direction_errors,
            "material_side_structure_exact_unit_count": structure_exact_units,
            "material_side_structure_exact_rate": round(structure_rate, 4),
            "factor_breakdown": factor_breakdown,
        },
        "thresholds": thresholds,
        "threshold_checks": threshold_checks,
        "threshold_passed": threshold_passed,
        "contract_fixture_passed": contract_fixture and threshold_passed,
        "real_agent_qualified": real_agent_qualified,
        "next_gate": (
            "qualified_response_may_enter_separate_shadow_scoring_review"
            if real_agent_qualified
            else "freeze_policy_then_use_new_sealed_holdout"
            if development_replay
            else "independent_blind_agent_run"
            if not independent and threshold_passed
            else "revise_agent_or_policy_then_rerun_blind_qualification"
        ),
        "unit_results": unit_results,
        "side_effect_audit": {
            "report_only": True,
            "score_computation_performed": False,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
    }
    report["report_sha256"] = canonical_hash(report)
    return report


def build_contract_fixture_response(
    worklist: Mapping[str, Any], gold_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """构造合同测试样例；该输出不得作为独立盲评证据。"""
    return {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "status": "factor_observation_agent_response_complete",
        "worklist_sha256": worklist["worklist_sha256"],
        "agent_policy_version": AGENT_POLICY_VERSION,
        "response_origin": "contract_fixture_from_human_calibration",
        "provider": "repository_contract_fixture",
        "model": "not_an_independent_agent_run",
        "blind_run_declarations": {
            "v3_factor_gold_accessed": True,
            "old_factor_proposals_accessed": True,
            "numeric_factor_values_supplied": False,
            "scoring_performed": False,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
        "results": [
            {
                "unit_ref": row["unit_ref"],
                "factor_materials": deepcopy(row["factor_materials"]),
            }
            for row in gold_manifest["factor_judgment_proposals"]
        ],
    }
