from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


CONTRACT_SCHEMA_VERSION = "i5b-opened-regression-contract-v2"
REPORT_SCHEMA_VERSION = "i5b-opened-regression-contract-report-v1"
FAILED_RULES = {
    "appointment_delegation",
    "talent_discovery",
    "tolerate_talent",
    "anti_nepotism",
}
EXPECTED_CONTRACT_VERSIONS = {
    "appointment_delegation": "appointment-delegation-factor-observation-v6",
    "talent_discovery": "talent-discovery-factor-agent-v2",
    "tolerate_talent": "tolerate-talent-factor-agent-v3",
    "anti_nepotism": "anti-nepotism-factor-agent-v2",
}
_EXACT_CLASSIFICATIONS = {"exact", "correct_abstention"}


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _artifact_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("opened regression artifact 越出仓库根目录") from exc
    if not path.is_file():
        raise ValueError(f"opened regression artifact 不存在: {relative}")
    return path


def _artifact_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_report(root: Path, relative: str) -> Mapping[str, Any]:
    payload = json.loads(_artifact_path(root, relative).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"opened regression report 格式非法: {relative}")
    return payload


def _mismatch_pairs(report: Mapping[str, Any]) -> set[tuple[str, str]]:
    pairs = {
        (str(row["unit_ref"]), str(row["field"]))
        for row in report.get("mismatches") or ()
    }
    for unit in report.get("unit_results") or ():
        unit_ref = str(unit["unit_ref"])
        if unit.get("material_side_structure_exact") is False:
            pairs.add((unit_ref, "material_side_structure"))
        for comparison in unit.get("factor_comparisons") or ():
            if comparison.get("classification") not in _EXACT_CLASSIFICATIONS:
                pairs.add((unit_ref, str(comparison["factor_name"])))
    return pairs


def _validate_shared_protocol(contract: Mapping[str, Any]) -> None:
    protocol = contract.get("legacy_protocol") or {}
    required = {
        "effective_use": "opened_regression_only",
        "old_gold_mutation_allowed": False,
        "sealed_rerun_allowed": False,
        "unbiased_qualification_claim_allowed": False,
        "new_samples_created": 0,
        "model_runs_authorized": 0,
    }
    if any(protocol.get(key) != value for key, value in required.items()):
        raise ValueError("opened sealed 协议不得允许后调、重跑或资格复用")


def _validate_appointment(contract: Mapping[str, Any]) -> None:
    semantics = contract.get("semantics") or {}
    if semantics.get("observation_slot_owner") != "upstream_contract":
        raise ValueError("appointment_delegation 必须由上游冻结 observation slot")
    if semantics.get("qualification_join_key") != "slot_id":
        raise ValueError("appointment_delegation qualification 必须按 slot_id join")
    if semantics.get("model_may_create_or_merge_slots") is not False:
        raise ValueError("appointment_delegation 不得让模型创建或合并 slot")
    if semantics.get("source_factor_owner") != "deterministic_lineage":
        raise ValueError("appointment_delegation source_factor 必须由 lineage 派生")
    if semantics.get("material_side_structure_exact_before_factor_comparison") is not True:
        raise ValueError("appointment_delegation 必须先验证材料侧结构")
    if set(semantics.get("slot_required_fields") or ()) != {
        "slot_id",
        "side",
        "episode_refs",
        "assertion_refs",
        "mechanical_observations",
    }:
        raise ValueError("appointment_delegation v6 slot 字段未收口")
    if set(semantics.get("mechanical_observation_required_fields") or ()) != {
        "jurisdiction_scope",
        "cross_domain",
        "institution_forming",
        "duration",
        "one_off_basis",
        "explicit_ruler_action",
        "scoped_responsibility",
        "linked_feedback",
        "distinct_authorization_count",
        "distinct_observation_count",
        "predecision_pressure_refs",
    }:
        raise ValueError("appointment_delegation v6 机械观察字段未收口")
    anchors = set(semantics.get("mechanical_anchor_factors") or ())
    if anchors != {
        "appointment_importance",
        "attribution_factor",
        "context_factor",
    }:
        raise ValueError("appointment_delegation 机械锚点因子不完整")


def _validate_talent_discovery(contract: Mapping[str, Any]) -> None:
    semantics = contract.get("semantics") or {}
    if tuple(semantics.get("recognition_timeline") or ()) != (
        "visibility_basis_at",
        "verification_at",
        "first_substantive_use_at",
    ):
        raise ValueError("talent_discovery 必须冻结完整识才时间轴")
    if semantics.get("verified_basis_requires_verification_before_first_use") is not True:
        raise ValueError("talent_discovery 使用前复核 Gate 缺失")
    if semantics.get("barrier_requires_explicit_barrier_and_crossing_action") is not True:
        raise ValueError("talent_discovery 不得从被召入反推准入障碍")
    expected = semantics.get("opened_regression_expectations") or {}
    if expected.get("TD-S01", {}).get("recognition_basis") != "missing_or_posthoc":
        raise ValueError("TD-S01 v2 回归预期未收口")
    if expected.get("TD-S02") != {
        "recognition_basis": "reputation_only_unverified",
        "barrier_crossing": "no_material_barrier",
    }:
        raise ValueError("TD-S02 v2 回归预期未收口")


def _validate_tolerate_talent(contract: Mapping[str, Any]) -> None:
    semantics = contract.get("semantics") or {}
    if "accepted_without_conflict" not in set(
        semantics.get("feedback_options_added") or ()
    ):
        raise ValueError("tolerate_talent 缺少无冲突采纳档")
    if "severe_threat_or_coercion" not in set(
        semantics.get("talent_safety_options_added") or ()
    ):
        raise ValueError("tolerate_talent 缺少严重威胁未决档")
    required_true = {
        "subject_ownership_required",
        "safe_without_retaliation_requires_positive_followup",
        "repair_or_continuity_requires_independent_followup",
        "absence_inference_for_safety_or_continuity_forbidden",
    }
    if any(semantics.get(key) is not True for key in required_true):
        raise ValueError("tolerate_talent 安全、修复或主体 Gate 不完整")
    if semantics.get("TT-S08_applicability") != "not_applicable":
        raise ValueError("TT-S08 必须固定为专业反馈链外反例")
    if set(semantics.get("subject_chain_observation_fields_required") or ()) != {
        "subject_ref",
        "assertion_refs",
        "order",
        "observation_id",
    }:
        raise ValueError("tolerate_talent v3 主体链观察字段未收口")
    if (
        semantics.get("positive_safety_followup_must_be_later_and_independent")
        is not True
        or semantics.get(
            "repair_or_continuity_followup_must_be_later_and_independent"
        )
        is not True
    ):
        raise ValueError("tolerate_talent v3 后续观察时间与独立性未收口")
    repair_required_true = {
        "repair_assessment_required_for_repair_tiers",
        "delayed_partial_requires_substantive_repair",
        "delayed_timing_requires_explicit_delay_basis",
        "formal_reversal_requires_formal_only_and_trust_not_restored",
        "formal_reversal_requires_later_independent_continuity",
        "formal_reversal_requires_bounded_nonrestoration_refs",
    }
    if any(semantics.get(key) is not True for key in repair_required_true):
        raise ValueError("tolerate_talent v3 修复相邻档 Gate 未收口")
    if set(semantics.get("repair_assessment_fields_required") or ()) != {
        "timing",
        "scope",
        "trust_restored",
    }:
        raise ValueError("tolerate_talent v3 修复评估字段未收口")
    expectations = semantics.get("opened_regression_expectations") or {}
    if set(expectations) != {f"TT-S0{index}" for index in range(1, 9)}:
        raise ValueError("tolerate_talent opened regression 预期覆盖不完整")
    factor_names = {
        "feedback_reception",
        "talent_safety",
        "professional_autonomy",
        "conflict_repair_continuity",
    }
    if any(set(expectations[unit_ref]) != factor_names for unit_ref in sorted(expectations)[:-1]):
        raise ValueError("tolerate_talent 因子预期必须显式完整")
    if expectations["TT-S08"] != {"applicability": "not_applicable"}:
        raise ValueError("TT-S08 回归预期必须为 not_applicable")


def _validate_anti_nepotism(contract: Mapping[str, Any]) -> None:
    semantics = contract.get("semantics") or {}
    ownership = semantics.get("factor_ownership") or {}
    if ownership != {
        "episode": [
            "capability_basis",
            "process_integrity",
            "public_power_exposure",
        ],
        "aggregate_context": ["network_effect"],
    }:
        raise ValueError("anti_nepotism context_kind 因子所有权未收口")
    if set(semantics.get("applicability_cases") or ()) != {
        "pollution_event",
        "prevention_event",
        "correction_event",
        "outside_rule",
        "unresolved",
    }:
        raise ValueError("anti_nepotism 适用性枚举不完整")
    thresholds = semantics.get("network_thresholds") or {}
    if thresholds.get("cross_person_single_channel") != {
        "min_people": 2,
        "exact_channels": 1,
    }:
        raise ValueError("anti_nepotism 单渠道网络门槛非法")
    if thresholds.get("cross_channel_capture") != {
        "min_people": 2,
        "min_channels": 2,
        "channel_control_refs_required": True,
    }:
        raise ValueError("anti_nepotism 跨渠道捕获门槛非法")
    if thresholds.get("durable_capture") != {
        "cross_channel_capture_required": True,
        "cross_period_or_repeated_evidence_required": True,
    }:
        raise ValueError("anti_nepotism 持续捕获门槛非法")
    if semantics.get("dismantled_by_ruler_requires_ruler_action_ref") is not True:
        raise ValueError("anti_nepotism 拆网必须绑定皇帝行动")
    observations = semantics.get("opened_regression_structural_observations") or {}
    if set(observations) != {"AN-S04", "AN-S05"}:
        raise ValueError("anti_nepotism 结构化回归观察覆盖非法")
    for unit_ref, observation in observations.items():
        if (
            not str(observation.get("private_relation_anchor") or "").strip()
            or int(observation.get("member_count_lower_bound") or 0) < 2
            or len(observation.get("channel_set") or ()) != 1
            or observation.get("observation_refs") != [f"{unit_ref}@A1"]
        ):
            raise ValueError(f"{unit_ref} 结构化人数、渠道或 lineage 非法")


_RULE_VALIDATORS = {
    "appointment_delegation": _validate_appointment,
    "talent_discovery": _validate_talent_discovery,
    "tolerate_talent": _validate_tolerate_talent,
    "anti_nepotism": _validate_anti_nepotism,
}


def evaluate_i5b_opened_regression_contract(
    contract: Mapping[str, Any], *, artifact_root: Path
) -> dict[str, Any]:
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("第五项 opened regression 合同版本非法")
    if contract.get("status") != "failed_rule_next_contracts_frozen":
        raise ValueError("第五项失败 rule 下一合同尚未冻结")
    _validate_shared_protocol(contract)

    pins = tuple(contract.get("artifact_pins") or ())
    if not pins:
        raise ValueError("opened regression 合同缺少旧资产 hash pin")
    pin_paths: set[str] = set()
    for pin in pins:
        relative = str(pin.get("path") or "")
        expected_hash = str(pin.get("sha256") or "")
        if not relative or relative in pin_paths or len(expected_hash) != 64:
            raise ValueError("opened regression artifact pin 非法或重复")
        pin_paths.add(relative)
        if _artifact_sha256(_artifact_path(artifact_root, relative)) != expected_hash:
            raise ValueError(f"opened regression 旧资产发生漂移: {relative}")

    rules = contract.get("rules") or {}
    if set(rules) != FAILED_RULES:
        raise ValueError("opened regression 合同必须覆盖四条失败 rule")

    rule_reports = []
    all_source_reports: set[str] = set()
    for rule_code in sorted(FAILED_RULES):
        rule = rules[rule_code]
        if (
            rule.get("contract_version") != EXPECTED_CONTRACT_VERSIONS[rule_code]
            or rule.get("effective_dataset_use") != "opened_regression_only"
            or rule.get("qualification_claim_allowed") is not False
            or int(rule.get("model_runs_authorized") or 0) != 0
        ):
            raise ValueError(f"{rule_code} 版本或 opened regression 状态非法")
        _RULE_VALIDATORS[rule_code](rule)

        observed_by_report: dict[str, set[tuple[str, str]]] = {}
        covered_fields: set[str] = set()
        observed_fields: set[str] = set()
        for source in rule.get("source_reports") or ():
            relative = str(source.get("path") or "")
            if relative not in pin_paths:
                raise ValueError(f"{rule_code} source report 未被 hash pin: {relative}")
            pairs = _mismatch_pairs(_load_report(artifact_root, relative))
            fields = {field for _, field in pairs}
            declared = set(source.get("covered_mismatch_fields") or ())
            if not pairs or declared != fields:
                raise ValueError(f"{rule_code} mismatch class 覆盖不完整: {relative}")
            observed_by_report[relative] = pairs
            observed_fields.update(fields)
            covered_fields.update(declared)
            all_source_reports.add(relative)

        cases = tuple(rule.get("representative_regression_cases") or ())
        if not cases:
            raise ValueError(f"{rule_code} 缺少代表性回归案例")
        for case in cases:
            source_report = str(case.get("source_report") or "")
            unit_ref = str(case.get("unit_ref") or "")
            fields = set(case.get("mismatch_fields") or ())
            if (
                source_report not in observed_by_report
                or not fields
                or not all(
                    (unit_ref, field) in observed_by_report[source_report]
                    for field in fields
                )
                or case.get("disposition")
                not in {
                    "contract_invariant_regression",
                    "legacy_gold_agreement",
                    "adjudication_required",
                    "legacy_qualifier_defect",
                }
            ):
                raise ValueError(f"{rule_code}/{unit_ref} 回归案例与旧报告不一致")

        rule_reports.append(
            {
                "rule_code": rule_code,
                "contract_version": rule["contract_version"],
                "source_report_count": len(observed_by_report),
                "covered_mismatch_fields": sorted(covered_fields),
                "representative_regression_case_count": len(cases),
                "effective_dataset_use": "opened_regression_only",
                "qualification_claim_allowed": False,
            }
        )

    pinned_reports = {
        path for path in pin_paths if path.endswith("qualification_report.json")
        or "qualification_report_" in path
    }
    if not all_source_reports <= pinned_reports:
        raise ValueError("opened regression source report pin 不完整")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "failed_rule_next_contracts_ready",
        "contract_sha256": _stable_hash(contract),
        "summary": {
            "tuned_failed_rule_count": len(rule_reports),
            "legacy_artifact_pin_count": len(pins),
            "opened_regression_source_report_count": len(all_source_reports),
            "model_runs_performed": 0,
            "new_samples_created": 0,
            "old_gold_modified": False,
            "sealed_reruns_performed": 0,
            "unbiased_qualification_claim_allowed": False,
            "formal_scoring_allowed": False,
            "database_write_count": 0,
        },
        "rules": rule_reports,
        "next_gate": "implement_contract_specific_v2_worklists_before_any_new_sealed_identity",
    }
