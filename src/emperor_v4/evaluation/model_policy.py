from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "model-policy-v2"
REPORT_SCHEMA_VERSION = "model-policy-report-v1"
ALLOWED_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{label} 必须是非空映射")
    return value


def validate_model_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"model policy schema 必须是 {SCHEMA_VERSION}")

    policy = _require_mapping(payload.get("model_policy"), "model_policy")
    allowed_uses = tuple(policy.get("allowed_uses") or ())
    if not allowed_uses or len(set(allowed_uses)) != len(allowed_uses):
        raise ValueError("model_policy.allowed_uses 必须非空且不重复")

    routing = _require_mapping(
        payload.get("workflow_agent_routing"), "workflow_agent_routing"
    )
    if routing.get("authority") != "draft_only":
        raise ValueError("workflow agent 只能拥有 draft_only 权限")
    task_contract = _require_mapping(routing.get("task_contract"), "task_contract")
    required_guards = (
        "explicit_stage_required",
        "explicit_model_argument_required",
        "explicit_reasoning_effort_required",
        "escalation_reason_required",
    )
    if not all(task_contract.get(name) is True for name in required_guards):
        raise ValueError("workflow agent task contract 缺少显式路由约束")
    forbidden_authority = (
        "worker_repository_write_allowed",
        "worker_formal_fact_acceptance_allowed",
        "worker_formal_scoring_allowed",
    )
    if not all(task_contract.get(name) is False for name in forbidden_authority):
        raise ValueError("workflow agent 不得获得仓库写入、正式事实或正式评分权限")

    profiles = _require_mapping(routing.get("profiles"), "workflow profiles")
    normalized_profiles: dict[str, dict[str, str]] = {}
    for code, profile_value in profiles.items():
        profile = _require_mapping(profile_value, f"profile {code}")
        model = str(profile.get("model") or "")
        effort = str(profile.get("reasoning_effort") or "")
        if not model.startswith("gpt-5.6-"):
            raise ValueError(f"profile {code} 未显式使用 GPT-5.6 系列")
        if effort not in ALLOWED_REASONING_EFFORTS:
            raise ValueError(f"profile {code} reasoning_effort 非法: {effort}")
        normalized_profiles[str(code)] = {"model": model, "reasoning_effort": effort}

    stages = _require_mapping(routing.get("stages"), "workflow stages")
    for stage_code, stage_value in stages.items():
        stage = _require_mapping(stage_value, f"stage {stage_code}")
        if stage.get("allowed_use") not in allowed_uses:
            raise ValueError(f"stage {stage_code} 未绑定允许的模型用途")
        primary = str(stage.get("primary_profile") or "")
        escalation = stage.get("escalation_profile")
        if primary not in normalized_profiles:
            raise ValueError(f"stage {stage_code} primary_profile 不存在")
        if escalation is not None and str(escalation) not in normalized_profiles:
            raise ValueError(f"stage {stage_code} escalation_profile 不存在")
        triggers = stage.get("escalation_triggers")
        if not isinstance(triggers, list) or len(set(triggers)) != len(triggers):
            raise ValueError(f"stage {stage_code} escalation_triggers 必须是不重复列表")
        if escalation is None and triggers:
            raise ValueError(f"stage {stage_code} 无升级模型却声明了升级条件")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed",
        "policy_schema_version": SCHEMA_VERSION,
        "policy_sha256": _stable_hash(payload),
        "profile_count": len(normalized_profiles),
        "stage_count": len(stages),
        "authority": "draft_only",
        "formal_fact_acceptance_allowed": False,
        "formal_scoring_allowed": False,
    }


def resolve_agent_route(
    payload: Mapping[str, Any],
    *,
    stage_code: str,
    escalation_reasons: Sequence[str] = (),
) -> dict[str, Any]:
    validation = validate_model_policy(payload)
    routing = payload["workflow_agent_routing"]
    stages = routing["stages"]
    if stage_code not in stages:
        raise ValueError(f"未知 workflow agent stage: {stage_code}")
    stage = stages[stage_code]
    declared_triggers = set(stage["escalation_triggers"])
    reasons = tuple(dict.fromkeys(str(item) for item in escalation_reasons if item))
    unknown = sorted(set(reasons) - declared_triggers)
    if unknown:
        raise ValueError(f"未声明的升级原因: {', '.join(unknown)}")
    escalated = bool(reasons)
    profile_code = (
        stage.get("escalation_profile") if escalated else stage["primary_profile"]
    )
    if profile_code is None:
        raise ValueError(f"stage {stage_code} 不允许继续升级")
    profile = routing["profiles"][profile_code]
    return {
        "schema_version": "agent-route-resolution-v1",
        "status": "resolved",
        "policy_sha256": validation["policy_sha256"],
        "stage_code": stage_code,
        "allowed_use": stage["allowed_use"],
        "profile_code": profile_code,
        "model": profile["model"],
        "reasoning_effort": profile["reasoning_effort"],
        "escalated": escalated,
        "escalation_reasons": list(reasons),
        "authority": routing["authority"],
        "repository_write_allowed": False,
        "formal_fact_acceptance_allowed": False,
        "formal_scoring_allowed": False,
    }
