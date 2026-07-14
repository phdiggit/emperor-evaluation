from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from emperor_v4.evaluation.talent_discovery_scoring import (
    FACTOR_NAMES,
    validate_scored_demo_manifest,
)


WORKLIST_SCHEMA_VERSION = "talent-discovery-factor-worklist-v1"
RESPONSE_SCHEMA_VERSION = "talent-discovery-factor-response-v1"
GOLD_SCHEMA_VERSION = "talent-discovery-factor-gold-v1"
REPORT_SCHEMA_VERSION = "talent-discovery-factor-qualification-report-v1"
POLICY_VERSION = "talent-discovery-factor-agent-v1"
APPLICABILITY_OPTIONS = {
    "applicable",
    "not_applicable",
    "insufficient_evidence",
}
FACTOR_OPTION_CATALOG = {
    "recognition_novelty": {
        "newly_visible_outsider": "此前不在统治者有效人才池中的外部人物首次进入视野",
        "cross_regime_or_camp_entry": "来自其他政权或敌对阵营的人物进入当前统治者人才池",
        "newly_visible_internal": "已在组织外围但此前未被当作可用人才的人物被识别",
        "established_core": "已经是核心或稳定受任者，本事件没有新增发现",
        "not_applicable": "整条事件不属于人才发现",
    },
    "recognition_basis": {
        "recommendation_verified_by_ruler": "荐举后由统治者在正式使用前亲自复核能力",
        "work_product_then_interview": "先从奏议、作品或实际方案识别能力，再追溯本人并面谈复核",
        "reputation_then_direct_demonstration": "先因声誉进入视野，再以当场陈述或作品展示能力",
        "direct_observation_or_interview": "统治者直接观察或面谈形成识才依据",
        "reputation_only_unverified": "只有声誉或名气，缺少使用前复核",
        "missing_or_posthoc": "缺少使用前依据，或只能由后世成就倒推",
        "not_applicable": "整条事件不属于人才发现",
    },
    "barrier_crossing": {
        "cross_camp_barrier_crossed": "明确跨越敌对阵营、旧政权或高风险政治来源障碍",
        "status_or_access_barrier_crossed": "跨越寒微身份、非正式渠道或组织准入障碍",
        "reluctance_or_access_barrier_crossed": "跨越拒绝出仕、难以接触或需要反复延揽的障碍",
        "no_material_barrier": "发现链成立，但没有需要单独奖励的实质障碍",
        "barrier_not_crossed": "存在实质障碍且未被克服",
        "not_applicable": "整条事件不属于人才发现",
    },
    "conversion_to_use": {
        "trial_then_scaled_use": "先试用或留用，再根据反馈扩大为稳定或重要职责",
        "direct_substantive_use": "识别后直接转化为有实际内容的任用或顾问职责",
        "limited_trial_or_symbolic": "只有有限试用、象征性安置或职责内容很弱",
        "no_conversion": "识别或称许没有转化为实际使用",
        "not_applicable": "整条事件不属于人才发现",
    },
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
            raise ValueError(f"人才发现因子响应包含禁止字段: {sorted(found)}")
        for value in payload.values():
            _assert_no_forbidden_keys(value)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for value in payload:
            _assert_no_forbidden_keys(value)


def build_talent_discovery_factor_worklist(
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    validate_scored_demo_manifest(manifest)
    passages = {row["passage_ref"]: row for row in manifest["source_passages"]}
    assertions = {row["assertion_ref"]: row for row in manifest["assertions"]}
    episodes = {row["episode_ref"]: row for row in manifest["historical_episodes"]}
    tasks = []
    for unit in sorted(manifest["rule_evidence_units"], key=lambda row: row["unit_ref"]):
        episode_rows = [episodes[ref] for ref in unit["episode_refs"]]
        assertion_refs = sorted(
            {
                ref
                for episode in episode_rows
                for ref in episode["assertion_refs"]
            }
        )
        tasks.append(
            {
                "unit_ref": unit["unit_ref"],
                "ruler": unit["ruler"],
                "person": unit["person"],
                "decision_arc_family": unit["decision_arc_family"],
                "episodes": [
                    {
                        key: episode[key]
                        for key in (
                            "episode_ref",
                            "action",
                            "responsibility",
                            "outcome",
                            "assertion_refs",
                        )
                    }
                    for episode in episode_rows
                ],
                "assertions": [
                    {
                        "assertion_ref": ref,
                        "summary": assertions[ref]["summary"],
                        "source": {
                            key: passages[assertions[ref]["source_passage_ref"]].get(
                                key
                            )
                            for key in (
                                "passage_ref",
                                "source_title",
                                "locator",
                                "url",
                                "revision_id",
                                "source_content_sha256",
                            )
                            if passages[assertions[ref]["source_passage_ref"]].get(key)
                            is not None
                        },
                    }
                    for ref in assertion_refs
                ],
            }
        )
    basis = {
        "policy_version": POLICY_VERSION,
        "rule_code": "talent_discovery",
        "factor_option_catalog": FACTOR_OPTION_CATALOG,
        "tasks": tasks,
    }
    return {
        "schema_version": WORKLIST_SCHEMA_VERSION,
        "status": "talent_discovery_open_worklist_ready",
        "task_code": "V4-TD-OPEN-DEVELOPMENT-FACTOR",
        "rule_code": "talent_discovery",
        "agent_policy_version": POLICY_VERSION,
        "input_boundary": {
            "gold_options_exposed": False,
            "numeric_values_exposed": False,
            "scores_or_rankings_exposed": False,
            "source_lineage_required": True,
        },
        "rule_boundary": {
            "coverage_unit": "一次独立发现或引入事件",
            "scoring_unit": "被发现人物的一次独立识别链",
            "exclude": [
                "普通升迁",
                "已有核心人才的常规任命或授权调整",
                "只有任官而无使用前识别依据",
                "以后世名声或结果倒推当时已经识才",
            ],
        },
        "applicability_options": sorted(APPLICABILITY_OPTIONS),
        "factor_option_catalog": FACTOR_OPTION_CATALOG,
        "output_contract": {
            "response_schema_version": RESPONSE_SCHEMA_VERSION,
            "factor_names": list(FACTOR_NAMES),
            "factor_fields": ["option_code", "reason", "assertion_refs"],
            "forbidden_keys": sorted(FORBIDDEN_KEYS),
        },
        "tasks": tasks,
        "worklist_sha256": _hash(basis),
    }


def build_talent_discovery_factor_batch_plan(
    worklist: Mapping[str, Any], *, max_units_per_batch: int = 4
) -> dict[str, Any]:
    if worklist.get("schema_version") != WORKLIST_SCHEMA_VERSION:
        raise ValueError("人才发现 worklist 版本非法")
    if max_units_per_batch < 1 or max_units_per_batch > 4:
        raise ValueError("人才发现每批评分单元必须在 1 到 4 之间")
    tasks = tuple(worklist.get("tasks") or ())
    batches = []
    for offset in range(0, len(tasks), max_units_per_batch):
        batch_tasks = list(tasks[offset : offset + max_units_per_batch])
        batch = {
            **{key: value for key, value in worklist.items() if key != "tasks"},
            "tasks": batch_tasks,
        }
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
        "schema_version": "talent-discovery-factor-batch-plan-v1",
        "status": "talent_discovery_factor_batch_plan_ready",
        "parent_worklist_sha256": worklist["worklist_sha256"],
        "max_units_per_batch": max_units_per_batch,
        "batch_count": len(batches),
        "batches": batches,
    }


def merge_talent_discovery_factor_responses(
    worklist: Mapping[str, Any], responses: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    results = [row for response in responses for row in response.get("results") or ()]
    merged = {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "status": "talent_discovery_factor_response_complete",
        "worklist_sha256": worklist["worklist_sha256"],
        "agent_policy_version": POLICY_VERSION,
        "response_origin": "open_development_agent_run",
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
    validate_talent_discovery_factor_response(worklist, merged)
    return merged


def validate_talent_discovery_factor_response(
    worklist: Mapping[str, Any], response: Mapping[str, Any]
) -> None:
    _assert_no_forbidden_keys(response)
    if (
        response.get("schema_version") != RESPONSE_SCHEMA_VERSION
        or response.get("status") != "talent_discovery_factor_response_complete"
        or response.get("worklist_sha256") != worklist.get("worklist_sha256")
        or response.get("agent_policy_version") != POLICY_VERSION
    ):
        raise ValueError("人才发现因子响应版本或 worklist 身份非法")
    expected_units = {row["unit_ref"]: row for row in worklist.get("tasks") or ()}
    results = tuple(response.get("results") or ())
    if {row.get("unit_ref") for row in results} != set(expected_units):
        raise ValueError("人才发现因子响应未完整唯一覆盖 worklist")
    for result in results:
        unit_ref = result["unit_ref"]
        applicability = result.get("applicability")
        if applicability not in APPLICABILITY_OPTIONS:
            raise ValueError(f"{unit_ref} applicability 非法")
        factors = result.get("factors") or {}
        if set(factors) != set(FACTOR_NAMES):
            raise ValueError(f"{unit_ref} 未完整覆盖四个发现因子")
        allowed_refs = {
            row["assertion_ref"] for row in expected_units[unit_ref]["assertions"]
        }
        for factor_name, factor in factors.items():
            if set(factor) != {"option_code", "reason", "assertion_refs"}:
                raise ValueError(f"{unit_ref}/{factor_name} 字段非法")
            option_code = factor["option_code"]
            if option_code not in FACTOR_OPTION_CATALOG[factor_name]:
                raise ValueError(f"{unit_ref}/{factor_name} option_code 非法")
            if not str(factor["reason"]).strip():
                raise ValueError(f"{unit_ref}/{factor_name} 缺少 reason")
            refs = tuple(factor["assertion_refs"])
            if len(refs) != len(set(refs)) or not set(refs) <= allowed_refs:
                raise ValueError(f"{unit_ref}/{factor_name} Assertion lineage 非法")
            if applicability == "not_applicable" and option_code != "not_applicable":
                raise ValueError(f"{unit_ref} 不适用时所有因子必须为 not_applicable")
            if applicability == "applicable" and option_code == "not_applicable":
                raise ValueError(f"{unit_ref} 适用时不得提交 not_applicable 因子")


def evaluate_talent_discovery_factor_qualification(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    gold: Mapping[str, Any],
) -> dict[str, Any]:
    validate_talent_discovery_factor_response(worklist, response)
    if (
        gold.get("schema_version") != GOLD_SCHEMA_VERSION
        or gold.get("status") != "frozen_open_development_gold"
        or gold.get("worklist_sha256") != worklist.get("worklist_sha256")
        or gold.get("agent_policy_version") != POLICY_VERSION
    ):
        raise ValueError("人才发现开放开发 Gold 版本或身份非法")
    expected = {row["unit_ref"]: row for row in gold.get("units") or ()}
    actual = {row["unit_ref"]: row for row in response.get("results") or ()}
    if set(expected) != set(actual):
        raise ValueError("人才发现 Gold 未完整覆盖响应")
    applicability_correct = 0
    factor_correct = 0
    factor_total = 0
    unsafe_false_applicable = 0
    mismatches = []
    by_factor: dict[str, Counter[str]] = {
        name: Counter() for name in FACTOR_NAMES
    }
    for unit_ref in sorted(expected):
        gold_row = expected[unit_ref]
        actual_row = actual[unit_ref]
        if actual_row["applicability"] == gold_row["applicability"]:
            applicability_correct += 1
        else:
            mismatches.append(
                {
                    "unit_ref": unit_ref,
                    "field": "applicability",
                    "gold": gold_row["applicability"],
                    "actual": actual_row["applicability"],
                }
            )
            if (
                gold_row["applicability"] == "not_applicable"
                and actual_row["applicability"] == "applicable"
            ):
                unsafe_false_applicable += 1
        for factor_name in FACTOR_NAMES:
            factor_total += 1
            gold_option = gold_row["factors"][factor_name]["option_code"]
            actual_option = actual_row["factors"][factor_name]["option_code"]
            matched = gold_option == actual_option
            by_factor[factor_name]["correct" if matched else "incorrect"] += 1
            factor_correct += int(matched)
            if not matched:
                mismatches.append(
                    {
                        "unit_ref": unit_ref,
                        "field": factor_name,
                        "gold": gold_option,
                        "actual": actual_option,
                    }
                )
    applicability_rate = round(applicability_correct / len(expected), 4)
    factor_rate = round(factor_correct / factor_total, 4)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "talent_discovery_open_development_evaluated",
        "agent_policy_version": POLICY_VERSION,
        "worklist_sha256": worklist["worklist_sha256"],
        "summary": {
            "unit_count": len(expected),
            "applicability_exact_count": applicability_correct,
            "applicability_exact_rate": applicability_rate,
            "factor_exact_count": factor_correct,
            "factor_comparison_count": factor_total,
            "factor_exact_rate": factor_rate,
            "unsafe_false_applicable_count": unsafe_false_applicable,
            "development_gate_passed": applicability_rate == 1.0
            and factor_rate >= 0.85
            and unsafe_false_applicable == 0,
        },
        "factor_breakdown": {
            name: {
                "correct": counts["correct"],
                "incorrect": counts["incorrect"],
                "exact_rate": round(counts["correct"] / sum(counts.values()), 4),
            }
            for name, counts in by_factor.items()
        },
        "mismatches": mismatches,
        "formal_scoring_allowed": False,
        "database_write_count": 0,
    }
