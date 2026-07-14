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
from emperor_v4.evaluation.factor_evidence_coverage import (
    COVERAGE_SCHEMA_VERSION,
    scope_coverage_to_sources,
    validate_coverage_declaration,
    validate_factor_resolution,
)


WORKLIST_SCHEMA_VERSION_V1 = "factor-observation-worklist-v1"
WORKLIST_SCHEMA_VERSION = "factor-observation-worklist-v2"
RESPONSE_SCHEMA_VERSION_V1 = "factor-observation-agent-response-v1"
RESPONSE_SCHEMA_VERSION = "factor-observation-agent-response-v2"
QUALIFICATION_SCHEMA_VERSION = "factor-observation-qualification-v2"
QUALIFICATION_GOLD_SCHEMA_VERSION = "factor-observation-qualification-gold-v2"
BATCH_PLAN_SCHEMA_VERSION = "factor-observation-batch-plan-v1"
AGENT_POLICY_VERSION_V1 = "appointment-delegation-factor-observation-agent-v1"
AGENT_POLICY_VERSION = "appointment-delegation-factor-observation-agent-v2"

OPTION_GUIDANCE_V1: dict[str, dict[str, str]] = {
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

OPTION_GUIDANCE: dict[str, dict[str, str]] = {
    "appointment_importance": {
        "nominal_or_light": "名义任用、轻量职责或影响范围很小；只按授权当时的责任域判断",
        "real_bounded": "真实职责成立但限于常规、局部或明确有限的责任域",
        "major_affairs": "直接承担重要军政事务、关键岗位或方面职责，但未达到国家全局关键授权",
        "critical_national_or_long_term": "直接承担国家全局、战略性地域或长期结构性关键授权；不得以后续成果、案件规模或政治影响反向抬档",
    },
    "appointment_effect": {
        "major_success": "任用—权责—反馈链直接证明异常显著的用人成功；重大任务、战役胜利或多次复用本身不自动抬档",
        "normal_success": "人岗适配和履职反馈明确；领域成果只作适配反馈，不在本规则重复结算",
        "weak_feedback": "存在正向履职信号，但反馈较弱、不完整或尚不足以确认稳定适配",
        "poor_result": "授权控制、监督或履职结果较差，但尚未证明任用直接造成重大损害",
        "major_direct_damage": "任用或授权安排与重大损害之间有直接、可归责的因果链",
        "structural_continuing_damage": "任用或授权安排直接造成跨期结构损害；后续清洗、案件扩大或领域灾难不得在因果链不完整时并入",
    },
    "continuity_factor": {
        "short_or_one_off": "仅有一次授权决定或短期任务；同一授权的直接履职后续不算跨阶段复用",
        "stable": "同一授权下存在稳定履职、持续反馈或延续监督，但没有至少两次可区分的授权或复用决定",
        "long_term_multi_stage": "证据直接覆盖至少两个可区分阶段的持续授权、续任或新任务复用；结果演变、失控、纠正或案件扩大不算复用阶段",
    },
    "attribution_factor": {
        "indirect": "皇帝责任成立，但关键判断受他人独立行为、争议因果或复杂链条显著影响",
        "direct": "任命、授权或反馈处置可直接归责于皇帝",
        "direct_under_pressure": "皇帝在明确反对、负面指控或现实约束下仍直接作出关键取舍；普通请求或进言不自动构成压力",
    },
    "source_factor": {
        "weak_or_compressed": "支撑本材料所声明判断的任用、职责、反馈或因果关键环节间接、压缩或缺失",
        "standard": "史源足以支持本材料的主要判断，但至少一个已声明语义环节不是直接完整覆盖",
        "complete_direct_chain": "史源直接覆盖本材料实际声明的任用、职责和反馈或损害链；按声明边界判断，不按史源数量、名气或材料外争议降档",
    },
    "context_factor": {
        "weak_but_applicable": "与规则相关，但任用机制或结算边界仍有明显缺口",
        "clear": "规则上下文、主责和不重复结算边界清楚",
        "core_mechanism_direct": "材料直接展示任用、授权与反馈的核心机制；不因领域成果重大而自动抬档",
    },
}

POLICY_OPTION_GUIDANCE = {
    AGENT_POLICY_VERSION_V1: OPTION_GUIDANCE_V1,
    AGENT_POLICY_VERSION: OPTION_GUIDANCE,
}

FACTOR_INFERENCE_POLICY = {
    "schema_version": "rule-factor-inference-policy-v1",
    "coverage_schema_version": COVERAGE_SCHEMA_VERSION,
    "decision_statuses": ["resolved", "insufficient_coverage"],
    "inference_bases": [
        "direct_evidence",
        "bounded_absence",
        "coverage_insufficient",
    ],
    "absence_sensitive_options": {
        "appointment_importance": [],
        "appointment_effect": [],
        "continuity_factor": ["short_or_one_off"],
        "attribution_factor": [],
        "source_factor": [],
        "context_factor": [],
    },
    "rule": (
        "正证据可在开放覆盖下确认；只有 reviewed_bounded_complete 且明确允许时，"
        "才可根据未发现材料选择缺失敏感选项。覆盖不足必须拒绝落档。"
    ),
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
    *,
    agent_policy_version: str = AGENT_POLICY_VERSION,
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
        task = {
            "unit_ref": unit_ref,
            "source_observation_fingerprint": observation_fingerprint(unit),
            "ruler": unit["ruler"],
            "person": unit["person"],
            "decision_arc_family": unit["decision_arc_family"],
            "episodes": task_episodes,
            "assertions": task_assertions,
            "prior_v4_judge_observations": deepcopy(unit["factor_observations"]),
        }
        if agent_policy_version != AGENT_POLICY_VERSION_V1:
            coverage = source_manifest.get("evidence_coverage") or {}
            task["evidence_coverage"] = scope_coverage_to_sources(
                coverage,
                [str(row["source"]["source_title"]) for row in task_assertions],
            )
        tasks.append(task)

    option_guidance = POLICY_OPTION_GUIDANCE.get(agent_policy_version)
    if option_guidance is None:
        raise ValueError("Factor Observation agent_policy_version 非法")
    semantic = {
        "schema_version": (
            WORKLIST_SCHEMA_VERSION_V1
            if agent_policy_version == AGENT_POLICY_VERSION_V1
            else WORKLIST_SCHEMA_VERSION
        ),
        "rule_code": RULE_CODE,
        "factor_schema_version": FACTOR_SCHEMA_VERSION,
        "agent_policy_version": agent_policy_version,
        "tasks": tasks,
        "factor_option_catalog": option_guidance,
    }
    if agent_policy_version != AGENT_POLICY_VERSION_V1:
        semantic["factor_inference_policy"] = deepcopy(FACTOR_INFERENCE_POLICY)
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
            "response_schema_version": (
                RESPONSE_SCHEMA_VERSION_V1
                if agent_policy_version == AGENT_POLICY_VERSION_V1
                else RESPONSE_SCHEMA_VERSION
            ),
            "required_result_fields": ["unit_ref", "factor_materials"],
            "factor_material_fields": ["material_code", "event_group", "side", "factors"],
            "factor_fields": (
                ["option_code", "reason", "assertion_refs"]
                if agent_policy_version == AGENT_POLICY_VERSION_V1
                else [
                    "decision_status",
                    "option_code",
                    "inference_basis",
                    "reason",
                    "assertion_refs",
                ]
            ),
            "forbidden_keys": sorted(FORBIDDEN_RESPONSE_KEYS),
        },
    }


def _worklist_semantic_payload(worklist: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
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
    if "factor_inference_policy" in worklist:
        payload["factor_inference_policy"] = deepcopy(
            worklist["factor_inference_policy"]
        )
    return payload


def build_factor_observation_batch_plan(
    source_manifest: Mapping[str, Any],
    *,
    max_units_per_batch: int = 4,
    max_workers: int = 4,
    agent_policy_version: str = AGENT_POLICY_VERSION,
) -> dict[str, Any]:
    """按稳定输入顺序建立可并发的受控微批计划，不执行模型调用。"""

    if max_units_per_batch <= 0 or max_workers <= 0:
        raise ValueError("Factor Observation 批大小和并发数必须为正整数")
    source_worklist = build_factor_observation_worklist(
        source_manifest, agent_policy_version=agent_policy_version
    )
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

    source_worklist = build_factor_observation_worklist(
        source_manifest,
        agent_policy_version=str(
            (batches[0].get("worklist") or {}).get("agent_policy_version") or ""
        ),
    )
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
    policy_version = str(worklist.get("agent_policy_version") or "")
    response_schema_version = (
        RESPONSE_SCHEMA_VERSION_V1
        if policy_version == AGENT_POLICY_VERSION_V1
        else RESPONSE_SCHEMA_VERSION
    )
    is_v2 = policy_version != AGENT_POLICY_VERSION_V1
    worklist_schema_version = (
        WORKLIST_SCHEMA_VERSION_V1 if not is_v2 else WORKLIST_SCHEMA_VERSION
    )
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
        worklist.get("schema_version") != worklist_schema_version
        or worklist.get("status") != "factor_observation_blind_worklist_ready"
        or response.get("schema_version") != response_schema_version
        or response.get("status") != "factor_observation_agent_response_complete"
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("agent_policy_version") != worklist.get("agent_policy_version")
        or worklist.get("factor_option_catalog")
        != POLICY_OPTION_GUIDANCE.get(str(worklist.get("agent_policy_version") or ""))
        or (
            is_v2
            and worklist.get("factor_inference_policy") != FACTOR_INFERENCE_POLICY
        )
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
    unresolved_count = 0
    parity_results = []
    for result in results:
        _require_exact_keys(
            result,
            {"unit_ref", "factor_materials"},
            f"{result.get('unit_ref')} result",
        )
        materials = tuple(result.get("factor_materials") or ())
        if not materials:
            raise ValueError(f"{result.get('unit_ref')} 缺少 factor_material")
        material_codes = [str(row.get("material_code") or "") for row in materials]
        if "" in material_codes or len(material_codes) != len(set(material_codes)):
            raise ValueError("factor_material code 缺失或重复")
        task = task_by_ref[str(result["unit_ref"])]
        allowed_assertions = {
            str(row["assertion_ref"]) for row in task.get("assertions") or ()
        }
        parity_materials = []
        for material in materials:
            _require_exact_keys(
                material,
                {"material_code", "event_group", "side", "factors"},
                f"{material.get('material_code')} factor_material",
            )
            if material.get("side") not in {"positive", "negative"} or not str(
                material.get("event_group") or ""
            ).strip():
                raise ValueError("factor_material side 或 event_group 非法")
            factors = material.get("factors") or {}
            if set(factors) != set(FACTOR_NAMES):
                raise ValueError("factor_material 必须完整覆盖有限因子")
            parity_factors = {}
            for factor_name, factor in factors.items():
                _require_exact_keys(
                    factor,
                    (
                        {
                            "decision_status",
                            "option_code",
                            "inference_basis",
                            "reason",
                            "assertion_refs",
                        }
                        if is_v2
                        else {"option_code", "reason", "assertion_refs"}
                    ),
                    f"{material.get('material_code')}.{factor_name}",
                )
                if not str(factor.get("reason") or "").strip():
                    raise ValueError("factor resolution 缺少 reason")
                refs = tuple(str(ref) for ref in factor.get("assertion_refs") or ())
                if len(refs) != len(set(refs)) or not set(refs) <= allowed_assertions:
                    raise ValueError("factor resolution Assertion lineage 重复或越界")
                if is_v2:
                    validate_factor_resolution(
                        coverage=task.get("evidence_coverage") or {},
                        decision_status=str(factor.get("decision_status") or ""),
                        option_code=factor.get("option_code"),
                        inference_basis=str(factor.get("inference_basis") or ""),
                        allowed_options=OPTION_ORDER[factor_name],
                        absence_sensitive_options=FACTOR_INFERENCE_POLICY[
                            "absence_sensitive_options"
                        ][factor_name],
                    )
                    if factor["decision_status"] == "insufficient_coverage":
                        unresolved_count += 1
                        continue
                    if factor["inference_basis"] == "direct_evidence" and not refs:
                        raise ValueError("直接证据因子必须携带 Assertion lineage")
                parity_factors[factor_name] = {
                    "option_code": factor["option_code"],
                    "reason": factor["reason"],
                    "assertion_refs": list(refs),
                }
            if len(parity_factors) == len(FACTOR_NAMES):
                parity_materials.append(
                    {
                        "material_code": material["material_code"],
                        "event_group": material["event_group"],
                        "side": material["side"],
                        "factors": parity_factors,
                    }
                )
        if len(parity_materials) == len(materials):
            parity_results.append(
                {"unit_ref": result["unit_ref"], "factor_materials": parity_materials}
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
            for result in parity_results
            for unit_ref in (str(result["unit_ref"]),)
        ],
    }
    if unresolved_count == 0:
        validate_parity_manifest(
            synthetic_manifest,
            source_manifest,
            allowed_proposal_statuses=frozenset({"agent_proposed_shadow"}),
            allowed_review_bases=frozenset({"blind_factor_observation_worklist"}),
        )
    for result in results:
        for material in result["factor_materials"]:
            effect_factor = material["factors"]["appointment_effect"]
            if is_v2 and effect_factor["decision_status"] == "insufficient_coverage":
                continue
            effect = effect_factor["option_code"]
            if material["side"] == "positive" and effect not in POSITIVE_EFFECT_OPTIONS:
                raise ValueError(f"{material['material_code']} side 与 effect 方向冲突")
            if material["side"] == "negative" and effect not in NEGATIVE_EFFECT_OPTIONS:
                raise ValueError(f"{material['material_code']} side 与 effect 方向冲突")


def build_factor_observation_qualification_gold(
    worklist: Mapping[str, Any],
    parity_gold_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    *,
    sample_role: str = "open_development",
) -> dict[str, Any]:
    """将已人工复核的档位 Gold 与 EvidenceCoverage 合成为资格 Gold v2。"""

    if (
        worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION
        or worklist.get("agent_policy_version") != AGENT_POLICY_VERSION
    ):
        raise ValueError("qualification Gold v2 只接受当前 v2 worklist")
    if sample_role not in {"open_development", "sealed_holdout"}:
        raise ValueError("qualification Gold sample_role 非法")
    validate_parity_manifest(parity_gold_manifest, source_manifest)
    fixture = build_contract_fixture_response(worklist, parity_gold_manifest)
    gold = {
        "schema_version": QUALIFICATION_GOLD_SCHEMA_VERSION,
        "status": "frozen_factor_observation_qualification_gold",
        "task_code": f"{worklist['task_code']}-GOLD-V2",
        "rule_code": RULE_CODE,
        "sample_role": sample_role,
        "worklist_sha256": worklist["worklist_sha256"],
        "agent_policy_version": worklist["agent_policy_version"],
        "source_manifest_ref": source_manifest.get("manifest_code"),
        "source_manifest_sha256": canonical_hash(source_manifest),
        "gold_origin": "human_reviewed_parity_gold_plus_coverage_adjudication",
        "units": deepcopy(fixture["results"]),
        "side_effect_audit": {
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
    }
    gold["gold_sha256"] = canonical_hash(gold)
    validate_factor_observation_qualification_gold(worklist, gold, source_manifest)
    return gold


def validate_factor_observation_qualification_gold(
    worklist: Mapping[str, Any],
    gold: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> None:
    _require_exact_keys(
        gold,
        {
            "schema_version",
            "status",
            "task_code",
            "rule_code",
            "sample_role",
            "worklist_sha256",
            "agent_policy_version",
            "source_manifest_ref",
            "source_manifest_sha256",
            "gold_origin",
            "units",
            "side_effect_audit",
            "gold_sha256",
        },
        "Factor Observation qualification Gold",
    )
    unsigned = dict(gold)
    stored_hash = unsigned.pop("gold_sha256")
    if (
        gold.get("schema_version") != QUALIFICATION_GOLD_SCHEMA_VERSION
        or gold.get("status") != "frozen_factor_observation_qualification_gold"
        or gold.get("task_code") != f"{worklist.get('task_code')}-GOLD-V2"
        or gold.get("rule_code") != RULE_CODE
        or gold.get("sample_role") not in {"open_development", "sealed_holdout"}
        or gold.get("worklist_sha256") != worklist.get("worklist_sha256")
        or gold.get("agent_policy_version") != worklist.get("agent_policy_version")
        or gold.get("source_manifest_ref") != source_manifest.get("manifest_code")
        or gold.get("source_manifest_sha256") != canonical_hash(source_manifest)
        or gold.get("gold_origin")
        != "human_reviewed_parity_gold_plus_coverage_adjudication"
        or gold.get("side_effect_audit")
        != {
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        }
        or stored_hash != canonical_hash(unsigned)
    ):
        raise ValueError("Factor Observation qualification Gold 绑定或版本非法")
    synthetic_response = {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "status": "factor_observation_agent_response_complete",
        "worklist_sha256": worklist["worklist_sha256"],
        "agent_policy_version": worklist["agent_policy_version"],
        "response_origin": "contract_fixture_from_human_calibration",
        "provider": "qualification_gold_validator",
        "model": "not_a_model_run",
        "blind_run_declarations": {
            "v3_factor_gold_accessed": True,
            "old_factor_proposals_accessed": True,
            "numeric_factor_values_supplied": False,
            "scoring_performed": False,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
        "results": deepcopy(gold.get("units") or ()),
    }
    validate_factor_observation_response(worklist, synthetic_response, source_manifest)


def evaluate_factor_observation_qualification(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    gold_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    validate_factor_observation_response(worklist, response, source_manifest)
    coverage_aware_gold = (
        gold_manifest.get("schema_version") == QUALIFICATION_GOLD_SCHEMA_VERSION
    )
    if coverage_aware_gold:
        validate_factor_observation_qualification_gold(
            worklist, gold_manifest, source_manifest
        )
        gold_rows = gold_manifest["units"]
    else:
        if worklist.get("agent_policy_version") != AGENT_POLICY_VERSION_V1:
            raise ValueError("v2 worklist 必须使用 coverage-aware qualification Gold v2")
        validate_parity_manifest(gold_manifest, source_manifest)
        gold_rows = gold_manifest["factor_judgment_proposals"]

    gold_by_unit = {row["unit_ref"]: row for row in gold_rows}
    response_by_unit = {row["unit_ref"]: row for row in response["results"]}
    exact = adjacent = nonadjacent = direction_errors = 0
    decision_total = decision_exact = 0
    false_resolutions = false_abstentions = correct_abstentions = 0
    resolved_option_total = 0
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
                    candidate_factor = candidate["factors"][factor_name]
                    gold_factor = gold["factors"][factor_name]
                    candidate_status = candidate_factor.get(
                        "decision_status", "resolved"
                    )
                    gold_status = gold_factor.get("decision_status", "resolved")
                    candidate_code = candidate_factor.get("option_code")
                    gold_code = gold_factor.get("option_code")
                    decision_total += 1
                    if candidate_status == gold_status:
                        decision_exact += 1
                    if (
                        gold_status == "insufficient_coverage"
                        and candidate_status == "resolved"
                    ):
                        classification = "unsafe_false_resolution"
                        false_resolutions += 1
                        factor_classifications[factor_name][classification] += 1
                    elif (
                        gold_status == "resolved"
                        and candidate_status == "insufficient_coverage"
                    ):
                        classification = "false_abstention"
                        false_abstentions += 1
                        factor_classifications[factor_name][classification] += 1
                    elif gold_status == candidate_status == "insufficient_coverage":
                        classification = "correct_abstention"
                        correct_abstentions += 1
                        factor_classifications[factor_name][classification] += 1
                    else:
                        resolved_option_total += 1
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
                            "candidate_decision_status": candidate_status,
                            "gold_decision_status": gold_status,
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
    exact_rate = exact / resolved_option_total if resolved_option_total else 0.0
    decision_accuracy = decision_exact / decision_total if decision_total else 0.0
    structure_rate = structure_exact_units / unit_count if unit_count else 0.0
    thresholds = {
        "decision_status_accuracy_min": 1.0,
        "unsafe_false_resolution_max": 0,
        "false_abstention_max": 0,
        "factor_exact_match_rate_min": 0.85,
        "material_side_structure_exact_rate_min": 1.0,
        "direction_error_max": 0,
        "nonadjacent_error_max": 0,
        "contract_validation_required": True,
    }
    threshold_checks = {
        "decision_status_accuracy": decision_accuracy
        >= thresholds["decision_status_accuracy_min"],
        "unsafe_false_resolution": false_resolutions
        <= thresholds["unsafe_false_resolution_max"],
        "false_abstention": false_abstentions
        <= thresholds["false_abstention_max"],
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
            "decision_status_exact_count": (
                counts["exact"]
                + counts["adjacent"]
                + counts["nonadjacent"]
                + counts["direction_error"]
                + counts["correct_abstention"]
            ),
            "correct_abstention_count": counts["correct_abstention"],
            "unsafe_false_resolution_count": counts["unsafe_false_resolution"],
            "false_abstention_count": counts["false_abstention"],
            "resolved_option_comparison_count": (
                counts["exact"]
                + counts["adjacent"]
                + counts["nonadjacent"]
                + counts["direction_error"]
            ),
            "exact_count": counts["exact"],
            "exact_rate": round(
                counts["exact"]
                / (
                    counts["exact"]
                    + counts["adjacent"]
                    + counts["nonadjacent"]
                    + counts["direction_error"]
                )
                if (
                    counts["exact"]
                    + counts["adjacent"]
                    + counts["nonadjacent"]
                    + counts["direction_error"]
                )
                else 0.0,
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
        "qualification_gold_sha256": gold_manifest.get("gold_sha256"),
        "sample_role": gold_manifest.get("sample_role", "legacy_v1_development"),
        "response_origin": response["response_origin"],
        "provider": response["provider"],
        "model": response["model"],
        "metrics": {
            "unit_count": unit_count,
            "factor_comparison_count": decision_total,
            "decision_status_exact_count": decision_exact,
            "decision_status_accuracy": round(decision_accuracy, 4),
            "correct_abstention_count": correct_abstentions,
            "unsafe_false_resolution_count": false_resolutions,
            "false_abstention_count": false_abstentions,
            "resolved_option_comparison_count": resolved_option_total,
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
            "eliminate_unsafe_false_resolution_before_rerun"
            if false_resolutions
            else "add_direct_evidence_or_fix_false_abstention_before_rerun"
            if false_abstentions
            else "qualified_response_may_enter_separate_shadow_scoring_review"
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
    is_v2 = worklist.get("agent_policy_version") != AGENT_POLICY_VERSION_V1
    task_by_ref = {row["unit_ref"]: row for row in worklist["tasks"]}
    results = []
    for row in gold_manifest["factor_judgment_proposals"]:
        materials = deepcopy(row["factor_materials"])
        if is_v2:
            coverage = task_by_ref[row["unit_ref"]]["evidence_coverage"]
            for material in materials:
                for factor_name, factor in material["factors"].items():
                    absence_sensitive = factor["option_code"] in FACTOR_INFERENCE_POLICY[
                        "absence_sensitive_options"
                    ][factor_name]
                    if absence_sensitive and not coverage["absence_inference_allowed"]:
                        factor["decision_status"] = "insufficient_coverage"
                        factor["option_code"] = None
                        factor["inference_basis"] = "coverage_insufficient"
                        factor["assertion_refs"] = []
                        factor["reason"] = (
                            "当前为开放证据快照，不能根据未发现延续材料确认缺失敏感档位。"
                        )
                    else:
                        factor["decision_status"] = "resolved"
                        factor["inference_basis"] = (
                            "bounded_absence"
                            if absence_sensitive
                            else "direct_evidence"
                        )
        results.append({"unit_ref": row["unit_ref"], "factor_materials": materials})
    return {
        "schema_version": (
            RESPONSE_SCHEMA_VERSION if is_v2 else RESPONSE_SCHEMA_VERSION_V1
        ),
        "status": "factor_observation_agent_response_complete",
        "worklist_sha256": worklist["worklist_sha256"],
        "agent_policy_version": worklist["agent_policy_version"],
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
        "results": results,
    }
