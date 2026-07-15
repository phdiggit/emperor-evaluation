from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest
import yaml

from emperor_v4.application.appointment_delegation_v3_parity_runner import (
    run_appointment_delegation_v3_parity_shadow,
)
from emperor_v4.eval import main as eval_main
from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash
from emperor_v4.evaluation.appointment_delegation_v3_parity import (
    validate_parity_manifest,
)
from emperor_v4.evaluation.appointment_factor_v6 import (
    CONTRACT_VERSION as APPOINTMENT_FACTOR_V6_CONTRACT_VERSION,
    MODEL_FACTOR_NAMES as APPOINTMENT_FACTOR_V6_MODEL_FACTORS,
    RESPONSE_SCHEMA_VERSION as APPOINTMENT_FACTOR_V6_RESPONSE_SCHEMA_VERSION,
    build_appointment_factor_v6_gold,
    build_appointment_factor_v6_worklist,
    evaluate_appointment_factor_v6_qualification,
)
from emperor_v4.evaluation.factor_observation_agent import (
    AGENT_POLICY_VERSION,
    AGENT_POLICY_VERSION_V1,
    AGENT_POLICY_VERSION_V2,
    build_factor_observation_batch_plan,
    build_factor_observation_qualification_gold,
    build_contract_fixture_response,
    build_factor_observation_worklist,
    evaluate_factor_observation_qualification,
    merge_factor_observation_batch_responses,
    validate_factor_observation_response,
    validate_factor_observation_qualification_gold,
)
from emperor_v4.evaluation.factor_representativeness import (
    evaluate_factor_representativeness_plan,
)


ROOT = Path(__file__).resolve().parents[1]
PARITY_MANIFEST = (
    ROOT / "eval" / "appointment_delegation_v3_parity_demo" / "manifest.yml"
)
SOURCE_MANIFEST = (
    ROOT / "eval" / "appointment_delegation_scored_demo" / "manifest.yml"
)
OPEN_DEVELOPMENT_DIR = (
    ROOT / "eval" / "appointment_delegation_factor_open_development_v2"
)
SEALED_HOLDOUT_DIR = (
    ROOT / "eval" / "appointment_delegation_factor_sealed_holdout_v2"
)
REPRESENTATIVENESS_DIR = (
    ROOT / "eval" / "appointment_delegation_factor_representativeness"
)
OPEN_DEVELOPMENT_V3_DIR = (
    ROOT / "eval" / "appointment_delegation_factor_open_development_v3"
)
SEALED_HOLDOUT_V3_DIR = (
    ROOT / "eval" / "appointment_delegation_factor_sealed_holdout_v3"
)


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _reviewed_coverage_source() -> dict:
    source = _yaml(SOURCE_MANIFEST)
    source["evidence_coverage"].update(
        {
            "coverage_status": "reviewed_bounded_complete",
            "absence_inference_allowed": True,
            "covered_time_window": {"start": "前206", "end": "前195"},
            "stop_reason": "bounded_review_completed",
        }
    )
    return source


def _qualification_gold(worklist: dict, source: dict) -> dict:
    return build_factor_observation_qualification_gold(
        worklist, _yaml(PARITY_MANIFEST), source
    )


def test_v3_parity_shadow_restores_factor_resolution_and_reuses_v4_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = run_appointment_delegation_v3_parity_shadow(PARITY_MANIFEST)

    assert report["status"] == "appointment_delegation_v3_parity_shadow_ready"
    assert report["summary"] == {
        "ruler_count": 3,
        "rule_evidence_unit_count": 4,
        "judgment_proposal_count": 4,
        "score_contribution_count": 4,
        "factor_material_count": 5,
        "mixed_unit_count": 1,
        "baseline_distinct_unit_score_count": 2,
        "v3_parity_distinct_unit_score_count": 4,
        "model_call_count": 0,
        "database_write_count": 0,
        "formal_score_write_count": 0,
        "rebuilt_judgment_count": 4,
        "reused_judgment_count": 0,
        "rebuilt_score_contribution_count": 4,
        "reused_score_contribution_count": 0,
    }
    assert report["migration_contract"]["invalidated_from"] == "Judgment"
    assert report["migration_contract"]["agent_output_may_supply_numeric_values"] is False
    assert all(
        row["source_observation_fingerprint"]
        and row["prior_v4_observations"]
        and row["formal_acceptance_performed"] is False
        for row in report["judgments"]
    )

    comparison = {row["person"]: row for row in report["baseline_comparison"]}
    assert comparison["陈平"]["limited_factor_v1_normalized_contribution"] == 1.0
    assert comparison["韩信"]["limited_factor_v1_normalized_contribution"] == 1.0
    assert comparison["魏徵"]["limited_factor_v1_normalized_contribution"] == 1.0
    assert len(
        {
            comparison[name]["v3_parity_raw_net_before_density"]
            for name in ("陈平", "韩信", "魏徵")
        }
    ) == 3
    assert comparison["陈平"]["v3_parity_raw_net_before_density"] > comparison["魏徵"]["v3_parity_raw_net_before_density"] > comparison["韩信"]["v3_parity_raw_net_before_density"]

    lanyu = next(row for row in report["judgments"] if row["person"] == "蓝玉")
    assert {row["side"] for row in lanyu["factor_materials"]} == {
        "positive",
        "negative",
    }
    assert report["side_effect_audit"] == {
        "offline": True,
        "report_only": True,
        "model_call_count": 0,
        "database_write_count": 0,
        "formal_acceptance_performed": False,
        "formal_scoring_performed": False,
    }
    unsigned = dict(report)
    stored_hash = unsigned.pop("report_sha256")
    assert stored_hash == canonical_hash(unsigned)

    output = tmp_path / "v3-parity-report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "appointment-delegation-v3-parity-shadow",
            "--manifest",
            str(PARITY_MANIFEST),
            "--output",
            str(output),
        ],
    )
    assert eval_main() == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_v3_parity_proposal_cannot_supply_numeric_values() -> None:
    manifest = _yaml(PARITY_MANIFEST)
    source = _yaml(SOURCE_MANIFEST)
    invalid = deepcopy(manifest)
    invalid["factor_judgment_proposals"][0]["factor_materials"][0]["factors"][
        "appointment_importance"
    ]["value_num"] = 99

    with pytest.raises(ValueError, match="不得携带数值"):
        validate_parity_manifest(invalid, source)


def test_v3_parity_observation_change_invalidates_only_affected_judgment() -> None:
    manifest = _yaml(PARITY_MANIFEST)
    source = _yaml(SOURCE_MANIFEST)
    changed = deepcopy(source)
    changed["rule_evidence_units"][0]["factor_observations"]["authority_clarity"][
        "reason"
    ] += "（新证据改变观察）"

    with pytest.raises(ValueError, match="fingerprint 非法"):
        validate_parity_manifest(manifest, changed)


def test_v3_parity_proposals_must_cover_every_rule_evidence_unit_once() -> None:
    manifest = _yaml(PARITY_MANIFEST)
    source = _yaml(SOURCE_MANIFEST)
    missing = deepcopy(manifest)
    missing["factor_judgment_proposals"].pop()

    with pytest.raises(ValueError, match="完整且唯一覆盖"):
        validate_parity_manifest(missing, source)


def test_v3_parity_factor_change_rebuilds_only_one_judgment(
    tmp_path: Path,
) -> None:
    baseline = run_appointment_delegation_v3_parity_shadow(PARITY_MANIFEST)
    prior_path = tmp_path / "prior-report.json"
    prior_path.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    candidate = _yaml(PARITY_MANIFEST)
    candidate["manifest_code"] = "appointment_delegation_v3_parity_candidate_v1"
    candidate["source_scored_manifest_path"] = str(SOURCE_MANIFEST.resolve())
    hanxin = next(
        row
        for row in candidate["factor_judgment_proposals"]
        if row["unit_ref"] == "REU-LB-HANXIN-QI-AUTHORITY-v1"
    )
    continuity = hanxin["factor_materials"][0]["factors"]["continuity_factor"]
    continuity["option_code"] = "stable"
    continuity["reason"] = "候选差异：把当前职责反馈按稳定授权复核。"
    candidate_path = tmp_path / "candidate.yml"
    candidate_path.write_text(
        yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    report = run_appointment_delegation_v3_parity_shadow(
        candidate_path, prior_report_path=prior_path
    )

    assert report["summary"]["rebuilt_judgment_count"] == 1
    assert report["summary"]["reused_judgment_count"] == 3
    assert report["summary"]["rebuilt_score_contribution_count"] == 1
    assert report["summary"]["reused_score_contribution_count"] == 3
    assert report["incremental_reuse"] == {
        "rebuilt_judgment_unit_refs": ["REU-LB-HANXIN-QI-AUTHORITY-v1"],
        "reused_judgment_unit_refs": [
            "REU-LB-CHENPING-AUTHORIZATION-v1",
            "REU-LSM-WEIZHENG-APPOINTMENT-v1",
            "REU-ZYZ-LANYU-AUTHORITY-v1",
        ],
        "rebuilt_score_contribution_unit_refs": [
            "REU-LB-HANXIN-QI-AUTHORITY-v1"
        ],
        "reused_score_contribution_unit_refs": [
            "REU-LB-CHENPING-AUTHORIZATION-v1",
            "REU-LSM-WEIZHENG-APPOINTMENT-v1",
            "REU-ZYZ-LANYU-AUTHORITY-v1",
        ],
        "unexpected_invalidation_count": 0,
    }
    prior_by_unit = {
        row["rule_evidence_unit_ref"]: row for row in baseline["judgments"]
    }
    current_by_unit = {
        row["rule_evidence_unit_ref"]: row for row in report["judgments"]
    }
    for unit_ref in report["incremental_reuse"]["reused_judgment_unit_refs"]:
        assert current_by_unit[unit_ref] == prior_by_unit[unit_ref]


def test_factor_observation_worklist_reuses_v4_judge_without_exposing_gold() -> None:
    source = _yaml(SOURCE_MANIFEST)
    worklist = build_factor_observation_worklist(source)

    assert worklist["status"] == "factor_observation_blind_worklist_ready"
    assert len(worklist["tasks"]) == 4
    assert worklist["input_boundary"] == {
        "uses_v4_judge_observations": True,
        "uses_assertion_lineage": True,
        "v3_factor_gold_exposed": False,
        "numeric_factor_values_exposed": False,
        "scores_or_rankings_exposed": False,
    }
    serialized = json.dumps(
        {
            "tasks": worklist["tasks"],
            "factor_option_catalog": worklist["factor_option_catalog"],
        },
        ensure_ascii=False,
    )
    assert "human_reviewed_shadow" not in serialized
    assert "existing_v4_observations_plus_v3_calibration" not in serialized
    assert "deterministic_value" not in serialized
    assert '"1.4"' not in serialized
    assert all(
        task["prior_v4_judge_observations"]
        and task["assertions"]
        and task["episodes"]
        for task in worklist["tasks"]
    )
    assert all(
        task["evidence_coverage"]["source_families"]
        == sorted({row["source"]["source_title"] for row in task["assertions"]})
        for task in worklist["tasks"]
    )


def test_factor_observation_policy_v3_freezes_calibrated_tier_boundaries() -> None:
    source = _yaml(SOURCE_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    catalog = worklist["factor_option_catalog"]

    assert worklist["agent_policy_version"] == AGENT_POLICY_VERSION
    assert worklist["schema_version"] == "factor-observation-worklist-v2"
    assert worklist["output_contract"]["response_schema_version"] == (
        "factor-observation-agent-response-v2"
    )
    assert "不得以后续成果、案件规模或政治影响反向抬档" in catalog[
        "appointment_importance"
    ]["critical_national_or_long_term"]
    assert "领域成果只作适配反馈，不在本规则重复结算" in catalog[
        "appointment_effect"
    ]["normal_success"]
    assert "至少有两次可区分的皇帝授权" in catalog["continuity_factor"][
        "long_term_multi_stage"
    ]
    assert "至少有两个可区分" in catalog["continuity_factor"]["stable"]
    assert "同一战役" in catalog["continuity_factor"]["long_term_multi_stage"]
    assert worklist["factor_inference_policy"]["schema_version"] == (
        "rule-factor-inference-policy-v3"
    )
    assert "stable" in worklist["factor_inference_policy"][
        "continuity_positive_evidence_tests"
    ]
    assert "按声明边界判断" in catalog["source_factor"][
        "complete_direct_chain"
    ]

    gold = _yaml(PARITY_MANIFEST)
    proposals = {row["unit_ref"]: row for row in gold["factor_judgment_proposals"]}
    weizheng = proposals["REU-LSM-WEIZHENG-APPOINTMENT-v1"]["factor_materials"][0]
    chenping = proposals["REU-LB-CHENPING-AUTHORIZATION-v1"]["factor_materials"][0]
    assert (
        weizheng["factors"]["continuity_factor"]["option_code"]
        == "long_term_multi_stage"
    )
    assert chenping["factors"]["appointment_importance"]["option_code"] == "major_affairs"


def test_factor_observation_v1_policy_artifacts_remain_validatable() -> None:
    source = _yaml(SOURCE_MANIFEST)
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(
        source, agent_policy_version=AGENT_POLICY_VERSION_V1
    )
    response = build_contract_fixture_response(worklist, gold)

    assert worklist["agent_policy_version"] == AGENT_POLICY_VERSION_V1
    assert worklist["schema_version"] == "factor-observation-worklist-v1"
    assert response["agent_policy_version"] == AGENT_POLICY_VERSION_V1
    validate_factor_observation_response(worklist, response, source)


def test_factor_observation_batch_plan_keeps_four_unit_microbatches_parallel() -> None:
    source = _yaml(SOURCE_MANIFEST)
    plan = build_factor_observation_batch_plan(
        source, max_units_per_batch=2, max_workers=4
    )

    assert plan["status"] == "factor_observation_batch_plan_ready"
    assert plan["scheduling_policy"] == {
        "optimization_objective": "wall_clock_latency_first",
        "max_units_per_batch": 2,
        "requested_max_workers": 4,
        "effective_max_workers": 2,
        "batch_count": 2,
        "estimated_parallel_waves": 1,
        "token_accounting_required": True,
        "quality_gate_required": True,
    }
    unit_refs = [
        unit_ref for batch in plan["batches"] for unit_ref in batch["unit_refs"]
    ]
    assert unit_refs == [
        unit["unit_ref"] for unit in source["rule_evidence_units"]
    ]
    assert len(unit_refs) == len(set(unit_refs)) == 4
    assert all(len(batch["unit_refs"]) == 2 for batch in plan["batches"])
    assert len(
        {batch["worklist"]["worklist_sha256"] for batch in plan["batches"]}
    ) == 2
    assert plan["side_effect_audit"]["model_call_count"] == 0


def test_factor_observation_batch_responses_merge_into_original_worklist() -> None:
    source = _yaml(SOURCE_MANIFEST)
    gold = _yaml(PARITY_MANIFEST)
    plan = build_factor_observation_batch_plan(
        source, max_units_per_batch=2, max_workers=2
    )
    responses = []
    for batch in plan["batches"]:
        batch_gold = deepcopy(gold)
        batch_gold["factor_judgment_proposals"] = [
            row
            for row in gold["factor_judgment_proposals"]
            if row["unit_ref"] in batch["unit_refs"]
        ]
        responses.append(build_contract_fixture_response(batch["worklist"], batch_gold))

    merged = merge_factor_observation_batch_responses(plan, responses, source)
    full_worklist = build_factor_observation_worklist(source)

    assert merged == build_contract_fixture_response(full_worklist, gold)
    assert [row["unit_ref"] for row in merged["results"]] == [
        task["unit_ref"] for task in full_worklist["tasks"]
    ]


def test_factor_observation_open_snapshot_fixture_requires_coverage_review() -> None:
    source = _yaml(SOURCE_MANIFEST)
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    fixture = build_contract_fixture_response(worklist, gold)
    qualification_gold = _qualification_gold(worklist, source)

    report = evaluate_factor_observation_qualification(
        worklist, fixture, qualification_gold, source
    )

    assert report["status"] == "factor_observation_qualification_harness_ready"
    assert report["metrics"]["factor_comparison_count"] == 30
    assert report["metrics"]["decision_status_accuracy"] == 1.0
    assert report["metrics"]["correct_abstention_count"] == 1
    assert report["metrics"]["unsafe_false_resolution_count"] == 0
    assert report["metrics"]["false_abstention_count"] == 0
    assert report["metrics"]["resolved_option_comparison_count"] == 29
    assert report["metrics"]["factor_exact_match_rate"] == 1.0
    assert report["metrics"]["material_side_structure_exact_rate"] == 1.0
    assert report["threshold_passed"] is True
    assert report["contract_fixture_passed"] is True
    assert report["real_agent_qualified"] is False
    assert report["next_gate"] == "independent_blind_agent_run"
    assert report["side_effect_audit"]["score_computation_performed"] is False


def test_factor_observation_independent_exact_response_can_pass_gate() -> None:
    source = _reviewed_coverage_source()
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    response = build_contract_fixture_response(worklist, gold)
    qualification_gold = _qualification_gold(worklist, source)
    response["response_origin"] = "independent_blind_agent_run"
    response["provider"] = "test_provider"
    response["model"] = "test_model"
    response["blind_run_declarations"]["v3_factor_gold_accessed"] = False
    response["blind_run_declarations"]["old_factor_proposals_accessed"] = False

    report = evaluate_factor_observation_qualification(
        worklist, response, qualification_gold, source
    )

    assert report["status"] == "factor_observation_agent_qualified"
    assert report["real_agent_qualified"] is True
    assert report["contract_fixture_passed"] is False


def test_factor_observation_development_replay_never_qualifies() -> None:
    source = _reviewed_coverage_source()
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    response = build_contract_fixture_response(worklist, gold)
    qualification_gold = _qualification_gold(worklist, source)
    response["response_origin"] = "development_replay_after_gold_opened"
    response["provider"] = "test_provider"
    response["model"] = "explicit_test_model"
    response["blind_run_declarations"]["v3_factor_gold_accessed"] = False
    response["blind_run_declarations"]["old_factor_proposals_accessed"] = False

    report = evaluate_factor_observation_qualification(
        worklist, response, qualification_gold, source
    )

    assert report["threshold_passed"] is True
    assert report["status"] == "factor_observation_development_replay_completed"
    assert report["contract_fixture_passed"] is False
    assert report["real_agent_qualified"] is False
    assert report["next_gate"] == "freeze_policy_then_use_new_sealed_holdout"


def test_factor_observation_response_rejects_numeric_injection() -> None:
    source = _yaml(SOURCE_MANIFEST)
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    response = build_contract_fixture_response(worklist, gold)
    response["results"][0]["factor_materials"][0]["factors"][
        "appointment_importance"
    ]["numeric_value"] = 99

    with pytest.raises(ValueError, match="不得携带数值或排名字段"):
        validate_factor_observation_response(worklist, response, source)

    unknown_numeric = build_contract_fixture_response(worklist, gold)
    unknown_numeric["results"][0]["factor_materials"][0]["confidence"] = 0.99
    with pytest.raises(ValueError, match="字段必须严格匹配"):
        validate_factor_observation_response(worklist, unknown_numeric, source)


def test_factor_observation_response_rejects_gold_leakage_claim_in_blind_run() -> None:
    source = _yaml(SOURCE_MANIFEST)
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    response = build_contract_fixture_response(worklist, gold)
    response["response_origin"] = "independent_blind_agent_run"

    with pytest.raises(ValueError, match="盲评与副作用声明非法"):
        validate_factor_observation_response(worklist, response, source)


def test_factor_observation_response_requires_complete_coverage_and_direction() -> None:
    source = _yaml(SOURCE_MANIFEST)
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    missing = build_contract_fixture_response(worklist, gold)
    missing["results"].pop()

    with pytest.raises(ValueError, match="完整且唯一覆盖"):
        validate_factor_observation_response(worklist, missing, source)

    wrong_direction = build_contract_fixture_response(worklist, gold)
    wrong_direction["results"][0]["factor_materials"][0]["factors"][
        "appointment_effect"
    ]["option_code"] = "poor_result"
    with pytest.raises(ValueError, match="方向冲突"):
        validate_factor_observation_response(worklist, wrong_direction, source)


def test_qualification_gold_v2_separates_unsafe_resolution_and_false_abstention():
    source = _yaml(SOURCE_MANIFEST)
    parity_gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    qualification_gold = _qualification_gold(worklist, source)
    validate_factor_observation_qualification_gold(
        worklist, qualification_gold, source
    )
    wrong_task = deepcopy(qualification_gold)
    wrong_task["task_code"] = "V4-AD-WRONG-GOLD-V2"
    unsigned = dict(wrong_task)
    unsigned.pop("gold_sha256")
    wrong_task["gold_sha256"] = canonical_hash(unsigned)
    with pytest.raises(ValueError, match="绑定或版本非法"):
        validate_factor_observation_qualification_gold(worklist, wrong_task, source)

    unsafe = build_contract_fixture_response(worklist, parity_gold)
    hanxin = next(
        row for row in unsafe["results"] if row["unit_ref"] == "REU-LB-HANXIN-QI-AUTHORITY-v1"
    )
    continuity = hanxin["factor_materials"][0]["factors"]["continuity_factor"]
    continuity.update(
        {
            "decision_status": "resolved",
            "option_code": "short_or_one_off",
            "inference_basis": "direct_evidence",
            "reason": "测试用错误强判。",
            "assertion_refs": ["CLMEXT-D63C5BDADE6A7EA5@CLM-HX-QIWANG-APPOINT"],
        }
    )
    unsafe_report = evaluate_factor_observation_qualification(
        worklist, unsafe, qualification_gold, source
    )
    assert unsafe_report["metrics"]["unsafe_false_resolution_count"] == 1
    assert unsafe_report["metrics"]["false_abstention_count"] == 0
    assert unsafe_report["threshold_passed"] is False
    assert unsafe_report["next_gate"] == (
        "eliminate_unsafe_false_resolution_before_rerun"
    )

    overcautious = build_contract_fixture_response(worklist, parity_gold)
    weizheng = next(
        row
        for row in overcautious["results"]
        if row["unit_ref"] == "REU-LSM-WEIZHENG-APPOINTMENT-v1"
    )
    continuity = weizheng["factor_materials"][0]["factors"]["continuity_factor"]
    continuity.update(
        {
            "decision_status": "insufficient_coverage",
            "option_code": None,
            "inference_basis": "coverage_insufficient",
            "reason": "测试用错误拒判。",
            "assertion_refs": [],
        }
    )
    overcautious_report = evaluate_factor_observation_qualification(
        worklist, overcautious, qualification_gold, source
    )
    assert overcautious_report["metrics"]["unsafe_false_resolution_count"] == 0
    assert overcautious_report["metrics"]["false_abstention_count"] == 1
    assert overcautious_report["threshold_passed"] is False
    assert overcautious_report["next_gate"] == (
        "add_direct_evidence_or_fix_false_abstention_before_rerun"
    )


def test_open_development_v2_is_reproducible_and_keeps_one_safe_abstention() -> None:
    source = _yaml(OPEN_DEVELOPMENT_DIR / "source_manifest.yml")
    factor_gold = _yaml(OPEN_DEVELOPMENT_DIR / "factor_gold.yml")
    tracked_worklist = json.loads(
        (OPEN_DEVELOPMENT_DIR / "worklist_v2.json").read_text(encoding="utf-8")
    )
    tracked_gold = json.loads(
        (OPEN_DEVELOPMENT_DIR / "qualification_gold_v2.json").read_text(
            encoding="utf-8"
        )
    )

    worklist = build_factor_observation_worklist(
        source, agent_policy_version=AGENT_POLICY_VERSION_V2
    )
    assert worklist == tracked_worklist
    qualification_gold = build_factor_observation_qualification_gold(
        worklist, factor_gold, source, sample_role="open_development"
    )
    assert qualification_gold == tracked_gold

    fixture = build_contract_fixture_response(worklist, factor_gold)
    report = evaluate_factor_observation_qualification(
        worklist, fixture, qualification_gold, source
    )
    assert report["threshold_passed"] is True
    assert report["metrics"]["factor_comparison_count"] == 30
    assert report["metrics"]["resolved_option_comparison_count"] == 29
    assert report["metrics"]["correct_abstention_count"] == 1

    zhangliang = next(
        row
        for row in qualification_gold["units"]
        if row["unit_ref"] == "REU-LB-ZHANGLIANG-HANXIN-SEAL-v1"
    )
    assert zhangliang["factor_materials"][0]["factors"]["continuity_factor"] == {
        "decision_status": "insufficient_coverage",
        "option_code": None,
        "inference_basis": "coverage_insufficient",
        "reason": "当前为开放证据快照，不能根据未发现延续材料确认缺失敏感档位。",
        "assertion_refs": [],
    }
    lishanchang = next(
        row
        for row in qualification_gold["units"]
        if row["unit_ref"] == "REU-ZYZ-LISHANCHANG-CENTRAL-AUTHORITY-v1"
    )
    assert {material["side"] for material in lishanchang["factor_materials"]} == {
        "positive",
        "negative",
    }

    agent_response = json.loads(
        (OPEN_DEVELOPMENT_DIR / "agent_response.json").read_text(encoding="utf-8")
    )
    tracked_report = json.loads(
        (OPEN_DEVELOPMENT_DIR / "qualification_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        evaluate_factor_observation_qualification(
            worklist, agent_response, qualification_gold, source
        )
        == tracked_report
    )
    assert tracked_report["metrics"]["factor_exact_match_rate"] == 0.9655
    assert tracked_report["metrics"]["adjacent_error_count"] == 1
    assert tracked_report["real_agent_qualified"] is False

    audit = json.loads(
        (OPEN_DEVELOPMENT_DIR / "execution_audit.json").read_text(encoding="utf-8")
    )
    assert audit["duration_sec"] == 67.729
    assert audit["total_tokens"] == 24863
    for name, expected_hash in audit["artifact_sha256"].items():
        actual_hash = hashlib.sha256(
            (OPEN_DEVELOPMENT_DIR / name).read_bytes()
        ).hexdigest()
        assert actual_hash == expected_hash


def test_sealed_holdout_v2_freezes_gold_and_preserves_failed_qualification() -> None:
    source = _yaml(SEALED_HOLDOUT_DIR / "source_manifest.yml")
    factor_gold = _yaml(SEALED_HOLDOUT_DIR / "factor_gold.yml")
    tracked_worklist = json.loads(
        (SEALED_HOLDOUT_DIR / "worklist_v2.json").read_text(encoding="utf-8")
    )
    tracked_gold = json.loads(
        (SEALED_HOLDOUT_DIR / "qualification_gold_v2.json").read_text(
            encoding="utf-8"
        )
    )

    worklist = build_factor_observation_worklist(
        source, agent_policy_version=AGENT_POLICY_VERSION_V2
    )
    assert worklist == tracked_worklist
    qualification_gold = build_factor_observation_qualification_gold(
        worklist, factor_gold, source, sample_role="sealed_holdout"
    )
    assert qualification_gold == tracked_gold
    assert qualification_gold["sample_role"] == "sealed_holdout"
    assert factor_gold["gold_access_policy"] == {
        "visible_to_agent": False,
        "editable_after_agent_run": False,
        "post_run_policy_or_gold_tuning_allowed": False,
    }
    fixture = build_contract_fixture_response(worklist, factor_gold)
    report = evaluate_factor_observation_qualification(
        worklist, fixture, qualification_gold, source
    )
    assert report["threshold_passed"] is True
    assert report["real_agent_qualified"] is False
    assert report["metrics"]["unit_count"] == 4
    assert report["metrics"]["factor_comparison_count"] == 30
    assert report["metrics"]["resolved_option_comparison_count"] == 30
    assert report["metrics"]["correct_abstention_count"] == 0

    agent_response = json.loads(
        (SEALED_HOLDOUT_DIR / "agent_response.json").read_text(encoding="utf-8")
    )
    tracked_report = json.loads(
        (SEALED_HOLDOUT_DIR / "qualification_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        evaluate_factor_observation_qualification(
            worklist, agent_response, qualification_gold, source
        )
        == tracked_report
    )
    assert tracked_report["status"] == "factor_observation_agent_not_qualified"
    assert tracked_report["metrics"]["factor_exact_match_rate"] == 0.8333
    assert tracked_report["metrics"]["adjacent_error_count"] == 5
    assert tracked_report["metrics"]["nonadjacent_error_count"] == 0
    assert tracked_report["metrics"]["direction_error_count"] == 0
    assert tracked_report["real_agent_qualified"] is False

    audit = json.loads(
        (SEALED_HOLDOUT_DIR / "execution_audit.json").read_text(encoding="utf-8")
    )
    assert audit["pre_model_freeze_commit"] == "3bfc9b6"
    assert audit["sealed_model_run_count"] == 1
    assert audit["post_run_policy_or_gold_tuning_performed"] is False
    assert audit["duration_sec"] == 100.102
    assert audit["total_tokens"] == 26152
    for name, expected_hash in audit["artifact_sha256"].items():
        actual_hash = hashlib.sha256(
            (SEALED_HOLDOUT_DIR / name).read_bytes()
        ).hexdigest()
        assert actual_hash == expected_hash


def test_factor_representativeness_plan_counts_units_not_correlated_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _yaml(REPRESENTATIVENESS_DIR / "manifest.yml")
    report = evaluate_factor_representativeness_plan(manifest)
    tracked_report = json.loads(
        (REPRESENTATIVENESS_DIR / "report.json").read_text(encoding="utf-8")
    )

    assert report == tracked_report
    assert report["status"] == "factor_representativeness_sampling_plan_incomplete"
    assert report["summary"] == {
        "portfolio_unit_count": 32,
        "historical_opened_regression_unit_count": 12,
        "new_independent_unit_count": 20,
        "new_open_development_unit_count": 12,
        "future_sealed_unit_count": 8,
        "bound_candidate_count": 32,
        "unbound_candidate_count": 0,
        "sealed_identity_exposure_count": 8,
        "missing_stratum_count": 4,
    }
    assert report["performance_estimate"] == {
        "basis": "sealed_holdout_v2_observed_single_batch",
        "units_per_call": 4,
        "max_workers": 4,
        "estimated_model_call_count": 5,
        "estimated_parallel_wave_count": 2,
        "estimated_model_wall_clock_sec": 200.204,
        "estimated_total_tokens": 130760,
        "human_source_and_gold_review_excluded": True,
    }
    assert len(report["missing_strata"]) == 4
    assert report["candidate_sourcing_ready"] is True
    assert report["sealed_candidate_sourcing_ready"] is True
    assert report["qualification_claim_allowed"] is False

    leaked = deepcopy(manifest)
    sealed = next(
        row for row in leaked["sample_entries"] if row["group"] == "future_sealed"
    )
    sealed["expected_factor_options"] = {"continuity_factor": "stable"}
    with pytest.raises(ValueError, match="不得包含 Gold"):
        evaluate_factor_representativeness_plan(leaked)

    rebound = deepcopy(manifest)
    planned = next(
        row for row in rebound["sample_entries"] if row["group"] == "future_sealed"
    )
    planned["slot_type"] = "planned_slot"
    with pytest.raises(ValueError, match="不得预填候选身份"):
        evaluate_factor_representativeness_plan(rebound)

    cli_output = tmp_path / "representativeness.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "emperor-v4-eval",
            "appointment-delegation-factor-representativeness",
            "--manifest",
            str(REPRESENTATIVENESS_DIR / "manifest.yml"),
            "--output",
            str(cli_output),
        ],
    )
    assert eval_main() == 0
    assert json.loads(cli_output.read_text(encoding="utf-8")) == tracked_report


def test_stratified_open_development_v3_is_reproducible_before_factor_run() -> None:
    source = _yaml(OPEN_DEVELOPMENT_V3_DIR / "source_manifest.yml")
    factor_gold = _yaml(OPEN_DEVELOPMENT_V3_DIR / "factor_gold.yml")
    tracked_worklist = json.loads(
        (OPEN_DEVELOPMENT_V3_DIR / "worklist_v2.json").read_text(encoding="utf-8")
    )
    tracked_gold = json.loads(
        (OPEN_DEVELOPMENT_V3_DIR / "qualification_gold_v2.json").read_text(
            encoding="utf-8"
        )
    )

    worklist = build_factor_observation_worklist(source)
    assert worklist == tracked_worklist
    qualification_gold = build_factor_observation_qualification_gold(
        worklist, factor_gold, source, sample_role="open_development"
    )
    assert qualification_gold == tracked_gold
    assert len(worklist["tasks"]) == 12
    assert sum(
        len(row["factor_materials"])
        for row in factor_gold["factor_judgment_proposals"]
    ) == 16
    assert sum(
        len(material["factors"])
        for row in factor_gold["factor_judgment_proposals"]
        for material in row["factor_materials"]
    ) == 96

    fixture = build_contract_fixture_response(worklist, factor_gold)
    report = evaluate_factor_observation_qualification(
        worklist, fixture, qualification_gold, source
    )
    assert report["threshold_passed"] is True
    assert report["real_agent_qualified"] is False
    assert report["metrics"]["factor_comparison_count"] == 96

    source_review_hash = hashlib.sha256(
        (OPEN_DEVELOPMENT_V3_DIR / "source_review.json").read_bytes()
    ).hexdigest()
    assert source["frozen_basis"]["source_review_sha256"] == source_review_hash
    audit = json.loads(
        (OPEN_DEVELOPMENT_V3_DIR / "source_draft_execution_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit["task_count"] == 3
    assert audit["contract_valid_candidate_count"] == 12
    assert audit["quote_recovery_count"] == 3
    assert audit["wall_clock_duration_sec"] == 113.412
    assert audit["total_tokens"] == 211828


def test_stratified_sealed_holdout_v3_is_frozen_before_factor_run() -> None:
    source = _yaml(SEALED_HOLDOUT_V3_DIR / "source_manifest.yml")
    factor_gold = _yaml(SEALED_HOLDOUT_V3_DIR / "factor_gold.yml")
    tracked_worklist = json.loads(
        (SEALED_HOLDOUT_V3_DIR / "worklist_v2.json").read_text(encoding="utf-8")
    )
    tracked_gold = json.loads(
        (SEALED_HOLDOUT_V3_DIR / "qualification_gold_v2.json").read_text(
            encoding="utf-8"
        )
    )

    worklist = build_factor_observation_worklist(source)
    assert worklist == tracked_worklist
    qualification_gold = build_factor_observation_qualification_gold(
        worklist, factor_gold, source, sample_role="sealed_holdout"
    )
    assert qualification_gold == tracked_gold
    assert len(worklist["tasks"]) == 8
    assert sum(
        len(row["factor_materials"])
        for row in factor_gold["factor_judgment_proposals"]
    ) == 17
    assert sum(
        len(material["factors"])
        for row in factor_gold["factor_judgment_proposals"]
        for material in row["factor_materials"]
    ) == 102
    assert factor_gold["gold_access_policy"] == {
        "visible_to_agent": False,
        "editable_after_agent_run": False,
        "post_run_policy_or_gold_tuning_allowed": False,
    }
    response = json.loads(
        (SEALED_HOLDOUT_V3_DIR / "agent_response.json").read_text(encoding="utf-8")
    )
    tracked_report = json.loads(
        (SEALED_HOLDOUT_V3_DIR / "qualification_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        evaluate_factor_observation_qualification(
            worklist, response, qualification_gold, source
        )
        == tracked_report
    )
    assert tracked_report["threshold_passed"] is False
    assert tracked_report["metrics"]["unit_count"] == 8
    assert tracked_report["metrics"]["factor_comparison_count"] == 54
    assert tracked_report["metrics"]["material_side_structure_exact_unit_count"] == 5
    assert tracked_report["metrics"]["factor_exact_match_rate"] == 0.7143
    assert tracked_report["metrics"]["unsafe_false_resolution_count"] == 0
    assert tracked_report["metrics"]["nonadjacent_error_count"] == 0
    assert tracked_report["metrics"]["direction_error_count"] == 0
    audit = json.loads(
        (SEALED_HOLDOUT_V3_DIR / "execution_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert audit["pre_model_freeze_commit"] == "80f0de8"
    assert audit["sealed_model_run_count"] == 1
    assert audit["post_run_policy_or_gold_tuning_performed"] is False
    assert audit["wall_clock_duration_sec"] == 107.369
    assert audit["total_tokens"] == 60796


def test_factor_observation_cli_builds_worklist_and_scores_contract_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _yaml(SOURCE_MANIFEST)
    gold = _yaml(PARITY_MANIFEST)
    worklist = build_factor_observation_worklist(source)
    fixture = build_contract_fixture_response(worklist, gold)
    qualification_gold = _qualification_gold(worklist, source)
    worklist_path = tmp_path / "worklist.json"
    response_path = tmp_path / "response.json"
    report_path = tmp_path / "report.json"
    gold_path = tmp_path / "qualification-gold.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "appointment-delegation-factor-worklist",
            "--source-manifest",
            str(SOURCE_MANIFEST),
            "--output",
            str(worklist_path),
        ],
    )
    assert eval_main() == 0
    assert json.loads(worklist_path.read_text(encoding="utf-8")) == worklist
    response_path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "appointment-delegation-factor-gold",
            "--worklist",
            str(worklist_path),
            "--parity-gold-manifest",
            str(PARITY_MANIFEST),
            "--source-manifest",
            str(SOURCE_MANIFEST),
            "--sample-role",
            "open_development",
            "--output",
            str(gold_path),
        ],
    )
    assert eval_main() == 0
    assert json.loads(gold_path.read_text(encoding="utf-8")) == qualification_gold
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "python -m emperor_v4.eval",
            "appointment-delegation-factor-qualification",
            "--worklist",
            str(worklist_path),
            "--response",
            str(response_path),
            "--gold-manifest",
            str(gold_path),
            "--source-manifest",
            str(SOURCE_MANIFEST),
            "--output",
            str(report_path),
        ],
    )
    assert eval_main() == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))[
        "status"
    ] == "factor_observation_qualification_harness_ready"


def _v6_resolution(option_code: str, assertion_ref: str) -> dict:
    return {
        "decision_status": "resolved",
        "option_code": option_code,
        "reason": "fixture direct evidence",
        "assertion_refs": [assertion_ref],
    }


def _v6_factor_slots() -> tuple[dict, list[dict]]:
    units = [
        {
            "unit_ref": "REU-V6-ONE",
            "slots": [
                {
                    "slot_id": "REU-V6-ONE:positive:appointment",
                    "side": "positive",
                    "episode_refs": ["HE-V6-ONE"],
                    "assertion_refs": ["AS-V6-ONE"],
                    "mechanical_observations": {
                        "jurisdiction_scope": "major_affairs",
                        "cross_domain": False,
                        "institution_forming": False,
                        "duration": "bounded",
                        "one_off_basis": "not_established",
                        "explicit_ruler_action": True,
                        "scoped_responsibility": True,
                        "linked_feedback": True,
                        "distinct_authorization_count": 1,
                        "distinct_observation_count": 2,
                        "predecision_pressure_refs": [],
                    },
                },
                {
                    "slot_id": "REU-V6-ONE:negative:damage",
                    "side": "negative",
                    "episode_refs": ["HE-V6-TWO"],
                    "assertion_refs": ["AS-V6-TWO"],
                    "mechanical_observations": {
                        "jurisdiction_scope": "major_affairs",
                        "cross_domain": False,
                        "institution_forming": False,
                        "duration": "bounded",
                        "one_off_basis": "not_established",
                        "explicit_ruler_action": True,
                        "scoped_responsibility": True,
                        "linked_feedback": True,
                        "distinct_authorization_count": 1,
                        "distinct_observation_count": 2,
                        "predecision_pressure_refs": [],
                    },
                },
            ],
        }
    ]
    source_factors = {
        "REU-V6-ONE:positive:appointment": _v6_resolution(
            "complete_direct_chain", "AS-V6-ONE"
        ),
        "REU-V6-ONE:negative:damage": _v6_resolution(
            "standard", "AS-V6-TWO"
        ),
    }
    worklist = build_appointment_factor_v6_worklist(
        task_code="AD-V6-OFFLINE-FIXTURE",
        units=units,
        deterministic_source_factors=source_factors,
    )
    options = {
        "appointment_importance": "major_affairs",
        "appointment_effect": "normal_success",
        "continuity_factor": "stable",
        "attribution_factor": "direct",
        "context_factor": "clear",
    }
    slots = []
    for slot in worklist["units"][0]["slots"]:
        assertion_ref = slot["assertion_refs"][0]
        slot_options = dict(options)
        if slot["side"] == "negative":
            slot_options["appointment_effect"] = "poor_result"
        slots.append(
            {
                "slot_id": slot["slot_id"],
                "side": slot["side"],
                "factors": {
                    factor_name: _v6_resolution(option, assertion_ref)
                    for factor_name, option in slot_options.items()
                },
            }
        )
    return worklist, slots


def _v6_response(worklist: dict, slots: list[dict]) -> dict:
    return {
        "schema_version": APPOINTMENT_FACTOR_V6_RESPONSE_SCHEMA_VERSION,
        "status": "factor_observation_response_complete",
        "contract_version": APPOINTMENT_FACTOR_V6_CONTRACT_VERSION,
        "worklist_sha256": worklist["worklist_sha256"],
        "response_origin": "offline_contract_fixture",
        "slots": slots,
    }


def test_appointment_factor_v6_freezes_slots_and_keeps_source_factor_deterministic():
    worklist, slots = _v6_factor_slots()

    assert worklist["qualification_join_key"] == "slot_id"
    assert worklist["source_factor_owner"] == "deterministic_lineage"
    assert "source_factor" not in APPOINTMENT_FACTOR_V6_MODEL_FACTORS
    assert all(
        set(slot) == {
            "slot_id",
            "side",
            "episode_refs",
            "assertion_refs",
            "mechanical_observations",
            "deterministic_factors",
        }
        and set(slot["deterministic_factors"]) == {"source_factor"}
        for unit in worklist["units"]
        for slot in unit["slots"]
    )
    assert all(
        set(slot["factors"]) == set(APPOINTMENT_FACTOR_V6_MODEL_FACTORS)
        for slot in slots
    )
    with pytest.raises(ValueError, match="只填写且完整覆盖允许的模型因子"):
        invalid_slots = deepcopy(slots)
        invalid_slots[0]["factors"]["source_factor"] = _v6_resolution(
            "standard", "AS-V6-ONE"
        )
        build_appointment_factor_v6_gold(worklist, invalid_slots)


def test_appointment_factor_v6_qualification_joins_by_slot_id_not_string_order():
    worklist, slots = _v6_factor_slots()
    gold = build_appointment_factor_v6_gold(worklist, slots)
    response_slots = list(reversed(deepcopy(slots)))

    report = evaluate_appointment_factor_v6_qualification(
        worklist, _v6_response(worklist, response_slots), gold
    )

    assert report["qualification_join_key"] == "slot_id"
    assert report["structure_diagnostics"] == {
        "missing_slot_ids": [],
        "extra_slot_ids": [],
        "side_mismatches": [],
        "structure_exact": True,
    }
    assert report["threshold_passed"] is True
    assert {row["slot_id"] for row in report["factor_comparisons"]} == {
        "REU-V6-ONE:positive:appointment",
        "REU-V6-ONE:negative:damage",
    }
    assert "candidate_event_group" not in report["factor_comparisons"][0]
    assert report["execution_audit"]["model_call_count"] == 0
    assert report["execution_audit"]["source_factor_compared_as_model_output"] is False


def test_appointment_factor_v6_reports_missing_extra_and_side_mismatch_separately():
    worklist, slots = _v6_factor_slots()
    gold = build_appointment_factor_v6_gold(worklist, slots)
    malformed = deepcopy(slots)
    malformed[0]["side"] = "negative"
    malformed.pop()
    extra = deepcopy(slots[1])
    extra["slot_id"] = "EXTRA-SLOT"
    malformed.append(extra)

    report = evaluate_appointment_factor_v6_qualification(
        worklist, _v6_response(worklist, malformed), gold
    )

    assert report["structure_diagnostics"] == {
        "missing_slot_ids": ["REU-V6-ONE:negative:damage"],
        "extra_slot_ids": ["EXTRA-SLOT"],
        "side_mismatches": [
            {
                "slot_id": "REU-V6-ONE:positive:appointment",
                "expected_side": "positive",
                "candidate_side": "negative",
            }
        ],
        "structure_exact": False,
    }
    assert report["factor_comparisons"] == []
    assert report["threshold_passed"] is False


def test_appointment_factor_v6_mechanical_observations_fail_closed():
    worklist, slots = _v6_factor_slots()

    unsupported = deepcopy(slots)
    unsupported[0]["factors"]["appointment_importance"] = _v6_resolution(
        "critical_national_or_long_term", "AS-V6-ONE"
    )
    with pytest.raises(ValueError, match="缺少 mechanical_observations 支撑"):
        build_appointment_factor_v6_gold(worklist, unsupported)

    no_feedback = deepcopy(worklist)
    no_feedback["units"][0]["slots"][0]["mechanical_observations"][
        "linked_feedback"
    ] = False
    no_feedback.pop("worklist_sha256")
    no_feedback["worklist_sha256"] = canonical_hash(no_feedback)
    with pytest.raises(
        ValueError, match="appointment_effect.normal_success 缺少 mechanical_observations 支撑"
    ):
        build_appointment_factor_v6_gold(no_feedback, slots)

    no_scoped_responsibility = deepcopy(worklist)
    no_scoped_responsibility["units"][0]["slots"][0][
        "mechanical_observations"
    ]["scoped_responsibility"] = False
    no_scoped_responsibility.pop("worklist_sha256")
    no_scoped_responsibility["worklist_sha256"] = canonical_hash(
        no_scoped_responsibility
    )
    core_context = deepcopy(slots)
    core_context[0]["factors"]["context_factor"] = _v6_resolution(
        "core_mechanism_direct", "AS-V6-ONE"
    )
    with pytest.raises(
        ValueError,
        match="context_factor.core_mechanism_direct 缺少 mechanical_observations 支撑",
    ):
        build_appointment_factor_v6_gold(no_scoped_responsibility, core_context)

    unsupported = deepcopy(slots)
    unsupported[0]["factors"]["continuity_factor"] = _v6_resolution(
        "long_term_multi_stage", "AS-V6-ONE"
    )
    with pytest.raises(ValueError, match="缺少 mechanical_observations 支撑"):
        build_appointment_factor_v6_gold(worklist, unsupported)

    unsupported = deepcopy(slots)
    unsupported[0]["factors"]["continuity_factor"] = _v6_resolution(
        "short_or_one_off", "AS-V6-ONE"
    )
    with pytest.raises(ValueError, match="缺少 mechanical_observations 支撑"):
        build_appointment_factor_v6_gold(worklist, unsupported)

    explicit_one_off = deepcopy(worklist)
    one_off_observations = explicit_one_off["units"][0]["slots"][0][
        "mechanical_observations"
    ]
    one_off_observations["duration"] = "one_off"
    one_off_observations["one_off_basis"] = "explicit_one_off"
    one_off_observations["distinct_observation_count"] = 1
    explicit_one_off.pop("worklist_sha256")
    explicit_one_off["worklist_sha256"] = canonical_hash(explicit_one_off)
    supported = deepcopy(slots)
    supported[0]["factors"]["continuity_factor"] = _v6_resolution(
        "short_or_one_off", "AS-V6-ONE"
    )
    build_appointment_factor_v6_gold(explicit_one_off, supported)

    unsupported = deepcopy(slots)
    unsupported[0]["factors"]["attribution_factor"] = _v6_resolution(
        "direct_under_pressure", "AS-V6-ONE"
    )
    with pytest.raises(ValueError, match="缺少 mechanical_observations 支撑"):
        build_appointment_factor_v6_gold(worklist, unsupported)

    invalid_units = [
        {
            "unit_ref": "REU-V6-INVALID",
            "slots": [
                {
                    "slot_id": "REU-V6-INVALID:positive",
                    "side": "positive",
                    "episode_refs": ["HE-V6-INVALID"],
                    "assertion_refs": ["AS-V6-INVALID"],
                    "mechanical_observations": {
                        "jurisdiction_scope": "local_bounded",
                        "cross_domain": False,
                        "institution_forming": False,
                        "duration": "one_off",
                        "one_off_basis": "explicit_one_off",
                        "explicit_ruler_action": True,
                        "scoped_responsibility": True,
                        "linked_feedback": False,
                        "distinct_authorization_count": 1,
                        "distinct_observation_count": 1,
                        "predecision_pressure_refs": ["AS-OUT-OF-SLOT"],
                    },
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="predecision_pressure_refs 越出冻结 slot"):
        build_appointment_factor_v6_worklist(
            task_code="AD-V6-INVALID",
            units=invalid_units,
            deterministic_source_factors={
                "REU-V6-INVALID:positive": _v6_resolution(
                    "standard", "AS-V6-INVALID"
                )
            },
        )
