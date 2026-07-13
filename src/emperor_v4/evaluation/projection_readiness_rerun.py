from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from emperor_v4.evaluation.projection_judgment_shadow import (
    JUDGMENT_SHADOW_POLICY_VERSION,
    JUDGMENT_SHADOW_SCHEMA_VERSION,
    PROJECTION_SHADOW_POLICY_VERSION,
    materialize_judgment_shadow_review,
)


PROJECTION_RERUN_POLICY_VERSION = "projection-shadow-incremental-rerun-v1"


def _hash(payload: object) -> str:
    rendered = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _projection_from_unit(unit: Mapping[str, Any]) -> dict[str, Any]:
    semantic = {
        "input_type": "rule_evidence_unit_draft",
        "input_ref": unit["unit_code"],
        "input_semantic_fingerprint": unit["semantic_fingerprint"],
        "rule_code": unit["rule_code"],
        "rule_version": unit["rule_version"],
        "evaluation_context": unit["evaluation_context"],
        "projection_policy_version": PROJECTION_SHADOW_POLICY_VERSION,
    }
    fingerprint = _hash(semantic)
    return {
        "projection_code": f"RPS-{fingerprint[:20].upper()}",
        **semantic,
        "projection_semantic_fingerprint": fingerprint,
        "applicability_status": "applicable",
        "projection_status": "draft",
        "projection_payload": {
            "ruler_ref": unit["ruler_ref"],
            "person_ref": unit["person_ref"],
            "decision_arc_family": unit["decision_arc_family"],
            "members": unit["members"],
            "included_link_refs": unit["included_link_refs"],
            "evidence_assertion_refs": unit["evidence_assertion_refs"],
            "context_assertion_refs": unit.get("context_assertion_refs") or [],
            "delta_source_passage_refs": unit.get("delta_source_passage_refs") or [],
            "question_readiness": unit["question_readiness"],
            "input_semantic_version": unit["semantic_version"],
            "input_evidence_version": unit["evidence_version"],
        },
    }


def build_incremental_projection_rerun_worklist(
    prior_worklist: Mapping[str, Any], rule_evidence_delta: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        prior_worklist.get("status") != "projection_judgment_shadow_worklist_ready"
        or prior_worklist.get("formal_projection_count") != 0
        or prior_worklist.get("formal_judgment_count") != 0
        or prior_worklist.get("score_count") != 0
        or prior_worklist.get("database_write_count") != 0
    ):
        raise ValueError("Projection rerun prior worklist 状态非法")
    if (
        rule_evidence_delta.get("status")
        != "rule_evidence_shadow_delta_ready_for_projection_rebuild"
        or rule_evidence_delta.get("shadow_delta_gate_passed") is not True
        or rule_evidence_delta.get("readiness_rerun_authorized") is not True
        or rule_evidence_delta.get("remaining_readiness_gap_count") != 0
        or rule_evidence_delta.get("duplicate_consumption_episode_refs") != []
        or rule_evidence_delta.get("formal_acceptance_performed") is not False
        or rule_evidence_delta.get("formal_projection_count") != 0
        or rule_evidence_delta.get("formal_judgment_count") != 0
        or rule_evidence_delta.get("score_count") != 0
        or rule_evidence_delta.get("database_write_count") != 0
    ):
        raise ValueError("Projection rerun RuleEvidenceUnit delta 未通过 Gate")

    prior_by_input = {
        str(row["input_ref"]): row for row in prior_worklist.get("projections") or ()
    }
    units = {
        str(row["unit_code"]): row
        for row in rule_evidence_delta.get("rule_evidence_unit_drafts") or ()
    }
    rebuild_refs = set(rule_evidence_delta.get("projection_rebuild_unit_refs") or ())
    unchanged_refs = set(rule_evidence_delta.get("unchanged_unit_refs") or ())
    if (
        set(units) != set(prior_by_input)
        or rebuild_refs & unchanged_refs
        or rebuild_refs | unchanged_refs != set(units)
        or len(rebuild_refs) != rule_evidence_delta.get("updated_unit_count")
        or len(unchanged_refs) != rule_evidence_delta.get("unchanged_unit_count")
    ):
        raise ValueError("Projection rerun rebuild/reuse 范围不完整或重叠")

    projections = []
    change_map = []
    rebuilt_codes = []
    reused_codes = []
    for unit_ref in sorted(units):
        prior = prior_by_input[unit_ref]
        unit = units[unit_ref]
        if unit_ref in unchanged_refs:
            if prior["input_semantic_fingerprint"] != unit["semantic_fingerprint"]:
                raise ValueError("Projection reuse 输入 fingerprint 已变化")
            projection = json.loads(
                json.dumps(prior, ensure_ascii=False, sort_keys=True)
            )
            reused_codes.append(projection["projection_code"])
            disposition = "cache_reused"
        else:
            if prior["input_semantic_fingerprint"] == unit["semantic_fingerprint"]:
                raise ValueError("Projection rebuild 输入 fingerprint 未变化")
            projection = _projection_from_unit(unit)
            if projection["projection_code"] == prior["projection_code"]:
                raise ValueError("Projection rebuild 未产生新 projection code")
            rebuilt_codes.append(projection["projection_code"])
            disposition = "rebuilt_from_semantic_delta"
        projections.append(projection)
        change_map.append(
            {
                "input_ref": unit_ref,
                "prior_projection_code": prior["projection_code"],
                "current_projection_code": projection["projection_code"],
                "cache_disposition": disposition,
                "prior_input_semantic_fingerprint": prior[
                    "input_semantic_fingerprint"
                ],
                "current_input_semantic_fingerprint": projection[
                    "input_semantic_fingerprint"
                ],
            }
        )

    basis = {
        "prior_projection_task_code": prior_worklist.get("task_code"),
        "source_rule_evidence_delta_sha256": _hash(rule_evidence_delta),
        "projection_codes": [row["projection_code"] for row in projections],
        "projection_rerun_policy_version": PROJECTION_RERUN_POLICY_VERSION,
    }
    worklist_hash = _hash(basis)
    return {
        "schema_version": 1,
        "status": "projection_judgment_shadow_rerun_worklist_ready",
        "task_code": f"G3H-PJ-RERUN-{worklist_hash[:20].upper()}",
        "worklist_sha256": worklist_hash,
        **basis,
        "projection_shadow_policy_version": PROJECTION_SHADOW_POLICY_VERSION,
        "judgment_shadow_policy_version": JUDGMENT_SHADOW_POLICY_VERSION,
        "judgment_shadow_schema_version": JUDGMENT_SHADOW_SCHEMA_VERSION,
        "projection_count": len(projections),
        "rebuilt_projection_count": len(rebuilt_codes),
        "reused_projection_count": len(reused_codes),
        "rebuilt_projection_codes": sorted(rebuilt_codes),
        "reused_projection_codes": sorted(reused_codes),
        "projection_change_map": change_map,
        "projections": projections,
        "gold_accessed": False,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }


def materialize_incremental_judgment_rerun(
    worklist: Mapping[str, Any],
    response: Mapping[str, Any],
    prior_response: Mapping[str, Any],
) -> dict[str, Any]:
    base = materialize_judgment_shadow_review(worklist, response)
    current_rows = {
        str(row["projection_code"]): row for row in response.get("results") or ()
    }
    prior_rows = {
        str(row["projection_code"]): row
        for row in prior_response.get("results") or ()
    }
    reused_codes = set(worklist.get("reused_projection_codes") or ())
    if any(
        code not in prior_rows or current_rows.get(code) != prior_rows[code]
        for code in reused_codes
    ):
        raise ValueError("Projection cache reuse 的 Judgment row 未逐字段复用")
    if (
        base["judgment_shadow_candidate_count"] != worklist.get("projection_count")
        or base["blocked_evidence_count"] != 0
        or base["blocked_rule_boundary_count"] != 0
    ):
        raise ValueError("增量 readiness rerun 尚有 blocked Projection")

    directions = [
        row["shadow_direction"] for row in base["judgment_shadow_candidates"]
    ]
    return {
        **base,
        "status": "incremental_judgment_shadow_rerun_passed",
        "rebuilt_projection_count": worklist["rebuilt_projection_count"],
        "reused_projection_count": worklist["reused_projection_count"],
        "reused_judgment_count": len(reused_codes),
        "rejudged_projection_count": worklist["rebuilt_projection_count"],
        "positive_direction_count": directions.count("positive"),
        "negative_direction_count": directions.count("negative"),
        "mixed_direction_count": directions.count("mixed"),
        "all_projection_readiness_passed": True,
        "formal_acceptance_performed": False,
        "formal_projection_count": 0,
        "formal_judgment_count": 0,
        "score_count": 0,
        "database_write_count": 0,
    }
