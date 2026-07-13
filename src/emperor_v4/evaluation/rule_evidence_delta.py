from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from typing import Any, Mapping

from emperor_v4.contracts.boundary import RuleEvidenceMember, RuleEvidenceUnitDraft


RULE_EVIDENCE_DELTA_POLICY_VERSION = "rule-evidence-shadow-delta-v1"


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _semantic_payload(unit: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "rule_code": unit["rule_code"],
        "rule_version": unit["rule_version"],
        "aggregation_policy_version": unit["aggregation_policy_version"],
        "evaluation_context": unit["evaluation_context"],
        "ruler_ref": unit["ruler_ref"],
        "person_ref": unit["person_ref"],
        "decision_arc_family": unit["decision_arc_family"],
        "members": unit["members"],
    }
    context_refs = list(unit.get("context_assertion_refs") or ())
    if context_refs:
        payload["context_assertion_refs"] = context_refs
    return payload


def _validate_upstream(
    rule_evidence_final: Mapping[str, Any],
    input_gate_worklist: Mapping[str, Any],
    input_gate_final: Mapping[str, Any],
) -> None:
    if (
        rule_evidence_final.get("status") != "rule_evidence_unit_shadow_ready"
        or rule_evidence_final.get("shadow_gate_passed") is not True
        or rule_evidence_final.get("formal_acceptance_performed") is not False
        or rule_evidence_final.get("formal_rule_evidence_unit_count") != 0
        or rule_evidence_final.get("formal_projection_count") != 0
        or rule_evidence_final.get("judgment_count") != 0
        or rule_evidence_final.get("score_count") != 0
        or rule_evidence_final.get("database_write_count") != 0
    ):
        raise ValueError("RuleEvidenceUnit delta 基线未通过 Gate 或存在副作用")
    if (
        input_gate_final.get("status")
        != "source_gap_input_gate_passed_for_shadow_delta"
        or input_gate_final.get("shadow_delta_authorized") is not True
        or input_gate_final.get("readiness_rerun_authorized") is not False
        or input_gate_final.get("unresolved_count") != 0
        or input_gate_final.get("rejected_count") != 0
        or input_gate_final.get("formal_acceptance_performed") is not False
        or input_gate_final.get("formal_assertion_count") != 0
        or input_gate_final.get("formal_episode_count") != 0
        or input_gate_final.get("formal_projection_count") != 0
        or input_gate_final.get("formal_judgment_count") != 0
        or input_gate_final.get("score_count") != 0
        or input_gate_final.get("database_write_count") != 0
        or input_gate_final.get("task_code") != input_gate_worklist.get("task_code")
    ):
        raise ValueError("RuleEvidenceUnit delta 输入 Gate 未通过或存在副作用")


def apply_rule_evidence_shadow_delta(
    rule_evidence_final: Mapping[str, Any],
    input_gate_worklist: Mapping[str, Any],
    input_gate_final: Mapping[str, Any],
) -> dict[str, Any]:
    """把 proposal-only 输入应用到 RuleEvidenceUnit shadow 副本并审计版本。"""

    _validate_upstream(rule_evidence_final, input_gate_worklist, input_gate_final)
    units = {
        str(row["unit_code"]): deepcopy(row)
        for row in rule_evidence_final.get("rule_evidence_unit_drafts") or ()
    }
    tasks = {
        str(row["gap_code"]): row for row in input_gate_worklist.get("tasks") or ()
    }
    deltas = {
        str(row["gap_code"]): row
        for row in input_gate_final.get("accepted_shadow_deltas") or ()
    }
    if (
        len(deltas) != input_gate_final.get("accepted_shadow_delta_count")
        or set(deltas) != set(tasks)
        or not deltas
    ):
        raise ValueError("RuleEvidenceUnit shadow delta 未完整且唯一覆盖 input Gate")

    updated_refs: list[str] = []
    new_episode_refs: list[str] = []
    context_assertion_refs: list[str] = []
    new_arc_refs: list[str] = []
    delta_lineage: list[dict[str, Any]] = []
    for gap_code in sorted(deltas):
        task = tasks[gap_code]
        delta = deltas[gap_code]
        unit_ref = str(task["input_ref"])
        if unit_ref not in units:
            raise ValueError("RuleEvidenceUnit shadow delta 指向未知 unit")
        unit = units[unit_ref]
        if unit_ref in updated_refs:
            raise ValueError("同一 RuleEvidenceUnit 在一次 delta 中被重复更新")
        updated_refs.append(unit_ref)

        old_fingerprint = str(unit["semantic_fingerprint"])
        old_semantic_version = int(unit["semantic_version"])
        old_evidence_version = int(unit["evidence_version"])
        members = [dict(row) for row in unit["members"]]
        evidence_refs = set(str(ref) for ref in unit.get("evidence_assertion_refs") or ())
        context_refs = set(str(ref) for ref in unit.get("context_assertion_refs") or ())
        included_links = set(str(ref) for ref in unit.get("included_link_refs") or ())
        scoring_arc_refs = set(str(ref) for ref in unit.get("scoring_arc_only_refs") or ())
        passage_refs: set[str] = set()

        boundary = delta["boundary_disposition"]
        assertion_ref: str | None = None
        episode_ref: str | None = None
        arc_ref: str | None = None
        if boundary == "episode_arc_member":
            arc = delta["episode_arc_review"]
            episode_ref = str(arc["candidate_episode_ref"])
            assertion_refs = [str(ref) for ref in arc["evidence_assertion_refs"]]
            passage_refs.update(str(ref) for ref in arc["source_passage_refs"])
            evidence_refs.update(assertion_refs)
            arc_ref = "G3F-ARC-" + _hash(
                {
                    "unit_ref": unit_ref,
                    "episode_ref": episode_ref,
                    "decision": arc["decision"],
                    "policy": RULE_EVIDENCE_DELTA_POLICY_VERSION,
                }
            )[:20].upper()
            members.append(
                {
                    "member_ref": episode_ref,
                    "member_type": "episode",
                    "member_role": delta["member_role"],
                }
            )
            included_links.add(arc_ref)
            scoring_arc_refs.add(arc_ref)
            new_episode_refs.append(episode_ref)
            new_arc_refs.append(arc_ref)
        elif boundary == "context_for_rule_evidence_unit":
            assertion_ref = str(delta["candidate_assertion"]["assertion_code"])
            evidence_refs.add(assertion_ref)
            context_refs.add(assertion_ref)
            passage_refs.add(str(delta["candidate_assertion"]["source_passage_ref"]))
            context_assertion_refs.append(assertion_ref)
        elif boundary == "core_of_new_episode":
            episode_ref = str(delta["proposed_episode_ref"])
            assertion_ref = str(delta["candidate_assertion"]["assertion_code"])
            evidence_refs.add(assertion_ref)
            passage_refs.add(str(delta["candidate_assertion"]["source_passage_ref"]))
            arc_ref = "G3F-ARC-" + _hash(
                {
                    "unit_ref": unit_ref,
                    "episode_ref": episode_ref,
                    "antecedent_refs": task["current_episode_refs"],
                    "policy": RULE_EVIDENCE_DELTA_POLICY_VERSION,
                }
            )[:20].upper()
            members.append(
                {
                    "member_ref": episode_ref,
                    "member_type": "episode",
                    "member_role": delta["member_role"],
                }
            )
            included_links.add(arc_ref)
            scoring_arc_refs.add(arc_ref)
            new_episode_refs.append(episode_ref)
            new_arc_refs.append(arc_ref)
        else:
            raise ValueError("RuleEvidenceUnit shadow delta boundary 非法")

        member_keys = [
            (row["member_ref"], row["member_type"], row["member_role"])
            for row in members
        ]
        member_refs = [row["member_ref"] for row in members]
        if len(member_keys) != len(set(member_keys)) or len(member_refs) != len(
            set(member_refs)
        ):
            raise ValueError("RuleEvidenceUnit shadow delta 产生重复 member")
        members = sorted(
            members,
            key=lambda row: (
                0 if row["member_type"] == "episode" else 1,
                str(row["member_ref"]),
                str(row["member_role"]),
            ),
        )
        unit["members"] = members
        unit["evidence_assertion_refs"] = sorted(evidence_refs)
        unit["context_assertion_refs"] = sorted(context_refs)
        unit["included_link_refs"] = sorted(included_links)
        unit["scoring_arc_only_refs"] = sorted(scoring_arc_refs)
        unit["delta_source_passage_refs"] = sorted(
            set(unit.get("delta_source_passage_refs") or ()) | passage_refs
        )
        readiness = dict(unit["question_readiness"])
        for question in task["open_readiness_questions"]:
            if readiness.get(question) != "evidence_gap":
                raise ValueError("RuleEvidenceUnit shadow delta 尝试覆盖非 gap readiness")
            readiness[question] = "ready"
        unit["question_readiness"] = readiness

        new_fingerprint = _hash(_semantic_payload(unit))
        if new_fingerprint == old_fingerprint:
            raise ValueError("评分语义 delta 未改变 semantic fingerprint")
        unit["semantic_fingerprint"] = new_fingerprint
        unit["semantic_version"] = old_semantic_version + 1
        unit["evidence_version"] = old_evidence_version + 1
        unit["lineage"] = {
            **dict(unit.get("lineage") or {}),
            "source_gap_input_gate_task_code": str(input_gate_final["task_code"]),
        }
        unit["provenance"] = {
            **dict(unit.get("provenance") or {}),
            "delta_policy_version": RULE_EVIDENCE_DELTA_POLICY_VERSION,
        }
        validated = RuleEvidenceUnitDraft(
            unit_code=unit["unit_code"],
            rule_code=unit["rule_code"],
            rule_version=unit["rule_version"],
            aggregation_policy_version=unit["aggregation_policy_version"],
            evaluation_context=unit["evaluation_context"],
            semantic_fingerprint=unit["semantic_fingerprint"],
            semantic_version=unit["semantic_version"],
            evidence_version=unit["evidence_version"],
            members=tuple(
                RuleEvidenceMember(
                    row["member_ref"], row["member_type"], row["member_role"]
                )
                for row in unit["members"]
            ),
            aggregation_reason=unit["aggregation_reason"],
            status=unit["status"],
            lineage=unit["lineage"],
            provenance=unit["provenance"],
        )
        validated_payload = asdict(validated)
        if validated_payload["unit_code"] != unit_ref:
            raise ValueError("RuleEvidenceUnit stable unit_code 被改变")
        delta_lineage.append(
            {
                "gap_code": gap_code,
                "unit_ref": unit_ref,
                "boundary_disposition": boundary,
                "new_episode_ref": episode_ref,
                "new_assertion_ref": assertion_ref,
                "new_arc_ref": arc_ref,
                "source_passage_refs": sorted(passage_refs),
                "old_semantic_fingerprint": old_fingerprint,
                "new_semantic_fingerprint": new_fingerprint,
                "semantic_version": unit["semantic_version"],
                "evidence_version": unit["evidence_version"],
            }
        )

    all_units = [units[code] for code in sorted(units)]
    episode_owners: dict[str, str] = {}
    duplicates: set[str] = set()
    for unit in all_units:
        for member in unit["members"]:
            if member["member_type"] != "episode":
                continue
            previous = episode_owners.setdefault(member["member_ref"], unit["unit_code"])
            if previous != unit["unit_code"]:
                duplicates.add(member["member_ref"])
    remaining_gaps = sum(
        value == "evidence_gap"
        for unit in all_units
        for value in unit["question_readiness"].values()
    )
    unchanged_refs = sorted(set(units) - set(updated_refs))
    gate_passed = not duplicates and remaining_gaps == 0 and len(updated_refs) == len(deltas)
    return {
        "schema_version": 1,
        "status": (
            "rule_evidence_shadow_delta_ready_for_projection_rebuild"
            if gate_passed
            else "rule_evidence_shadow_delta_failed_closed"
        ),
        "source_rule_evidence_task_code": rule_evidence_final.get("task_code"),
        "source_input_gate_task_code": input_gate_final.get("task_code"),
        "rule_evidence_delta_policy_version": RULE_EVIDENCE_DELTA_POLICY_VERSION,
        "draft_unit_count": len(all_units),
        "updated_unit_count": len(updated_refs),
        "unchanged_unit_count": len(unchanged_refs),
        "semantic_version_increment_count": len(updated_refs),
        "evidence_version_increment_count": len(updated_refs),
        "new_episode_member_count": len(new_episode_refs),
        "new_context_assertion_count": len(context_assertion_refs),
        "new_scoring_arc_count": len(new_arc_refs),
        "remaining_readiness_gap_count": remaining_gaps,
        "duplicate_consumption_episode_refs": sorted(duplicates),
        "projection_rebuild_unit_refs": sorted(updated_refs),
        "unchanged_unit_refs": unchanged_refs,
        "delta_lineage": delta_lineage,
        "rule_evidence_unit_drafts": all_units,
        "shadow_delta_gate_passed": gate_passed,
        "readiness_rerun_authorized": gate_passed,
        "formal_acceptance_performed": False,
        "formal_assertion_count": 0,
        "formal_episode_count": 0,
        "formal_relation_count": 0,
        "formal_rule_evidence_unit_count": 0,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
