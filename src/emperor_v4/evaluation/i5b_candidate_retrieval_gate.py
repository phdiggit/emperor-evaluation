from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


GATE_SCHEMA_VERSION = "i5b-candidate-retrieval-gate-v4"
AUDIT_SCHEMA_VERSION = "i5b-cross-rule-orphan-audit-v1"
REQUIRED_LANES = (
    "person_event",
    "institution_policy",
    "negative_counterexample",
    "cross_rule_orphan_audit",
)
INSTITUTION_REQUIRED_RULES = {
    "appointment_delegation",
    "talent_discovery",
    "tolerate_talent",
    "anti_nepotism",
    "team_building",
}
ALLOWED_TRIGGER_REASONS = {
    "initial_rule_requirement",
    "source_or_contract_changed",
    "cross_rule_orphan_detected",
    "human_refreeze_requested",
    "pre_closeout_audit",
}


def _stable_hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def build_cross_rule_orphan_audit(
    *,
    target_rule_code: str,
    routed_passages: Sequence[Mapping[str, Any]],
    candidate_passage_refs: Sequence[str],
) -> dict[str, Any]:
    """Find eligible cross-rule passages that never entered the target inventory.

    Route eligibility is supplied by the neutral router. This audit never creates a
    fact or silently changes rule ownership; it only blocks premature human freeze.
    """

    target = str(target_rule_code).strip().lower()
    if not target:
        raise ValueError("跨规则孤儿审计缺少目标 rule")
    bound = set(_strings(candidate_passage_refs))
    seen: set[str] = set()
    unresolved: list[dict[str, Any]] = []
    checked = 0
    for row in routed_passages:
        passage_ref = str(row.get("passage_ref") or "").strip()
        accepted_rules = {value.lower() for value in _strings(row.get("accepted_rules"))}
        eligible_rules = {value.lower() for value in _strings(row.get("eligible_rules"))}
        if (
            not passage_ref
            or passage_ref in seen
            or not accepted_rules
            or not eligible_rules
        ):
            raise ValueError("跨规则孤儿审计 passage 非法或重复")
        seen.add(passage_ref)
        checked += 1
        if target in eligible_rules and target not in accepted_rules and passage_ref not in bound:
            unresolved.append(
                {
                    "passage_ref": passage_ref,
                    "accepted_rules": sorted(accepted_rules),
                    "eligible_rules": sorted(eligible_rules),
                    "reason": "eligible_cross_rule_passage_missing_candidate_binding",
                }
            )

    payload = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "target_rule_code": target,
        "status": "complete",
        "checked_passage_count": checked,
        "candidate_binding_count": len(bound),
        "unresolved_orphan_count": len(unresolved),
        "unresolved_orphans": unresolved,
        "facts_accepted": 0,
        "database_write_count": 0,
        "model_call_count": 0,
    }
    payload["report_sha256"] = _stable_hash(payload)
    return payload


def validate_candidate_retrieval_gate(
    gate: Mapping[str, Any], *, rule_code: str
) -> dict[str, Any]:
    """Validate every retrieval lane before the candidate universe may freeze."""

    rule = str(rule_code).strip().lower()
    if gate.get("schema_version") != GATE_SCHEMA_VERSION:
        raise ValueError("候选检索门禁版本非法")
    if str(gate.get("rule_code") or "").strip().lower() != rule:
        raise ValueError("候选检索门禁 rule 不匹配")

    versions = gate.get("input_versions") or {}
    required_versions = {
        "source_catalog_version",
        "source_cache_fingerprint",
        "rule_semantics_version",
        "retrieval_contract_version",
        "scholarly_profile_version",
    }
    if set(versions) != required_versions or any(
        not str(versions[key] or "").strip() for key in required_versions
    ):
        raise ValueError("候选检索门禁缺少完整输入版本")

    reasons = set(_strings(gate.get("trigger_reasons")))
    if not reasons or not reasons <= ALLOWED_TRIGGER_REASONS:
        raise ValueError("候选检索触发原因非法")
    if "pre_closeout_audit" not in reasons:
        raise ValueError("候选冻结前必须执行收口审计")
    if rule in INSTITUTION_REQUIRED_RULES and "initial_rule_requirement" not in reasons:
        raise ValueError("制度检索适用规则必须在首轮触发制度通道")

    lanes = gate.get("retrieval_lanes") or {}
    if set(lanes) != set(REQUIRED_LANES):
        raise ValueError("候选检索通道不完整")
    for lane in REQUIRED_LANES:
        row = lanes.get(lane) or {}
        status = row.get("status")
        if lane == "institution_policy" and rule not in INSTITUTION_REQUIRED_RULES:
            allowed = {"complete", "skipped_not_applicable"}
        else:
            allowed = {"complete"}
        if status not in allowed:
            raise ValueError(f"候选检索通道未完成: {lane}")
        if not str(row.get("query_version") or "").strip():
            raise ValueError(f"候选检索通道缺少 query_version: {lane}")
        candidate_count = row.get("candidate_count")
        if not isinstance(candidate_count, int) or candidate_count < 0:
            raise ValueError(f"候选检索通道 candidate_count 非法: {lane}")
        judged_count = row.get("judged_candidate_count")
        unresolved_count = row.get("unresolved_candidate_count")
        if (
            not isinstance(judged_count, int)
            or judged_count < 0
            or not isinstance(unresolved_count, int)
            or unresolved_count < 0
            or judged_count != candidate_count
            or unresolved_count != 0
        ):
            raise ValueError(f"候选检索通道仍有未 judge 候选: {lane}")

    institution_lane = lanes["institution_policy"]
    if rule in INSTITUTION_REQUIRED_RULES:
        for field in ("positive_query_count", "negative_query_count"):
            if not isinstance(institution_lane.get(field), int) or institution_lane[field] <= 0:
                raise ValueError(f"制度检索缺少独立正反检索: {field}")
        scholarly = gate.get("scholar_guided_retrieval") or {}
        task_count = scholarly.get("task_count")
        if (
            scholarly.get("status") != "complete"
            or not isinstance(task_count, int)
            or task_count <= 0
            or scholarly.get("source_cache_routed_task_count") != task_count
            or scholarly.get("judge_bound_task_count") != task_count
            or len(str(scholarly.get("report_sha256") or "")) != 64
        ):
            raise ValueError("学术引导检索尚未完整接入 Source Cache 与 Judge")

    negative_lane = lanes["negative_counterexample"]
    if rule in {"appointment_delegation", "team_building"} and negative_lane[
        "candidate_count"
    ] > 0:
        harm = gate.get("delegated_harm_audit") or {}
        if (
            harm.get("status") != "complete"
            or not isinstance(harm.get("reviewed_incident_count"), int)
            or harm["reviewed_incident_count"] <= 0
            or harm.get("unresolved_incident_count") != 0
            or harm.get("cross_rule_duplicate_count") != 0
            or len(str(harm.get("report_sha256") or "")) != 64
        ):
            raise ValueError("委托损害归责、纠偏或跨rule去重审计未闭合")

    disposition = gate.get("disposition_audit") or {}
    total = disposition.get("candidate_count")
    judged = disposition.get("judged_candidate_count")
    unresolved = disposition.get("unresolved_candidate_count")
    if (
        not isinstance(total, int)
        or total < 0
        or judged != total
        or unresolved != 0
        or disposition.get("status") != "complete"
    ):
        raise ValueError("候选全集尚有未回源或未 judge 项")

    source_scope = gate.get("source_scope") or {}
    relevant = source_scope.get("relevant_chapter_count")
    dispositioned = source_scope.get("dispositioned_chapter_count")
    if (
        source_scope.get("chapter_inventory_frozen") is not True
        or not isinstance(relevant, int)
        or relevant < 0
        or dispositioned != relevant
    ):
        raise ValueError("相关篇章尚未全部处置")

    audit = gate.get("cross_rule_orphan_audit") or {}
    audit_without_hash = {
        key: value for key, value in audit.items() if key != "report_sha256"
    }
    if (
        audit.get("schema_version") != AUDIT_SCHEMA_VERSION
        or str(audit.get("target_rule_code") or "").lower() != rule
        or audit.get("status") != "complete"
        or audit.get("unresolved_orphan_count") != 0
        or audit.get("unresolved_orphans") != []
        or audit.get("report_sha256") != _stable_hash(audit_without_hash)
    ):
        raise ValueError("跨规则孤儿审计仍有未绑定候选")

    execution = gate.get("execution_audit") or {}
    network_request_count = execution.get("network_request_count")
    if not isinstance(network_request_count, int) or network_request_count < 0:
        raise ValueError("候选检索门禁 network_request_count 非法")
    for field in ("model_call_count", "business_write_count"):
        if execution.get(field) != 0:
            raise ValueError("候选检索门禁必须保持零模型、零业务写入")
    if gate.get("human_freeze_accepted") is not True or not str(
        gate.get("human_freeze_decision_ref") or ""
    ).strip():
        raise ValueError("候选全集尚未人工冻结接受")

    return {
        "retrieval_gate_complete": True,
        "retrieval_gate_fingerprint": _stable_hash(gate),
        "unresolved_cross_rule_orphan_count": 0,
        "unresolved_candidate_count": 0,
        "judged_candidate_count": judged,
        "institution_policy_status": lanes["institution_policy"]["status"],
        "scholar_guided_retrieval_status": (
            gate.get("scholar_guided_retrieval") or {}
        ).get("status"),
        "network_request_count": network_request_count,
        "trigger_reasons": sorted(reasons),
    }
