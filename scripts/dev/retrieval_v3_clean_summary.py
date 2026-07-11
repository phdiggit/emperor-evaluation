from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence


NEGATIVE_GAP_TYPES = {
    "negative_undercoverage",
    "needs_primary_source",
    "predicate_missing",
    "true_lack",
}


def sum_usage(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        for value in (row.get("taskgen_usage") or {}, row.get("judge_usage") or {}):
            if not isinstance(value, Mapping):
                continue
            for key, amount in value.items():
                if isinstance(amount, int):
                    totals[key] = totals.get(key, 0) + amount
    return totals


def text(value: Any) -> str:
    return str(value or "").strip()


def claim_code(row: Mapping[str, Any]) -> str:
    return text(row.get("claim_code"))


def usable_for_scoring(row: Mapping[str, Any]) -> bool:
    return row.get("usable_for_scoring_cluster", True) is not False


def gap_covers_negative_object(gaps: Sequence[Mapping[str, Any]], object_name: str) -> bool:
    for gap in gaps:
        if text(gap.get("object_name")) != object_name:
            continue
        if text(gap.get("gap_type")) in NEGATIVE_GAP_TYPES:
            return True
        if text(gap.get("family_code")) == "revoked_or_failed_delegate":
            return True
    return False


def judge_anomalies(judge_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = [row for row in judge_payload.get("claims") or [] if isinstance(row, Mapping)]
    bindings = [
        row
        for row in (judge_payload.get("primary_bindings") or judge_payload.get("bindings") or [])
        if isinstance(row, Mapping)
    ]
    gaps = [row for row in judge_payload.get("coverage_gaps") or [] if isinstance(row, Mapping)]
    bindings_by_claim: dict[str, list[Mapping[str, Any]]] = {}
    for binding in bindings:
        code = claim_code(binding)
        if code:
            bindings_by_claim.setdefault(code, []).append(binding)

    rows: list[dict[str, Any]] = []
    for claim in claims:
        code = claim_code(claim)
        object_name = text(claim.get("object_name"))
        direction = text(claim.get("direction"))
        claim_bindings = bindings_by_claim.get(code, [])
        scoring_bindings = [binding for binding in claim_bindings if usable_for_scoring(binding)]
        negative_scoring_bindings = [
            binding for binding in scoring_bindings if text(binding.get("direction")) == "negative"
        ]
        has_negative_gap = bool(object_name) and gap_covers_negative_object(gaps, object_name)

        if direction == "mixed":
            if scoring_bindings and not negative_scoring_bindings and not has_negative_gap:
                rows.append(
                    {
                        "severity": "block",
                        "code": "mixed_claim_not_split",
                        "claim_code": code,
                        "object_name": object_name,
                        "direction": direction,
                        "message": "mixed claim has scoring binding but no negative split binding or gap",
                    }
                )
            elif not has_negative_gap:
                rows.append(
                    {
                        "severity": "warning",
                        "code": "mixed_claim_needs_review",
                        "claim_code": code,
                        "object_name": object_name,
                        "direction": direction,
                        "message": "mixed claim should be split or explicitly queued",
                    }
                )
        elif direction == "negative" and claim_bindings and not negative_scoring_bindings and not has_negative_gap:
            rows.append(
                {
                    "severity": "warning",
                    "code": "negative_claim_not_scoring_without_gap",
                    "claim_code": code,
                    "object_name": object_name,
                    "direction": direction,
                    "message": "negative claim has no scoring binding and no negative coverage gap",
                }
            )
    return rows


def anomaly_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"block": 0, "warning": 0}
    for row in rows:
        severity = text(row.get("severity"))
        if severity in counts:
            counts[severity] += 1
    return counts


def summarize_person(
    *,
    task: Mapping[str, Any],
    person_dir: Path,
    rounds: Sequence[Mapping[str, Any]],
    taskgen: Mapping[str, Any] | None,
    final_candidates: Mapping[str, Any] | None,
    final_judge: Mapping[str, Any] | None,
    alias_round_limit_reached: bool,
) -> dict[str, Any]:
    candidate_payload = final_candidates or {}
    judge_payload = final_judge or {}
    coverage = candidate_payload.get("coverage") if isinstance(candidate_payload.get("coverage"), Mapping) else {}
    rule = task.get("rule") if isinstance(task.get("rule"), Mapping) else {}
    anomalies = judge_anomalies(judge_payload) if judge_payload else []
    anomaly_totals = anomaly_counts(anomalies)
    return {
        "name": task.get("emperor_name") or "",
        "target_code": task.get("target_code") or "",
        "rule_code": task.get("rule_code") or rule.get("rule_code") or "",
        "capture_mode": task.get("capture_mode") or "",
        "formal_consumption_source": (task.get("target_payload") or {}).get("formal_consumption_source")
        if isinstance(task.get("target_payload"), Mapping)
        else None,
        "run_dir": str(person_dir),
        "taskgen_elapsed_seconds": taskgen.get("elapsed_seconds") if taskgen else None,
        "taskgen_usage": taskgen.get("usage") if taskgen else {},
        "taskgen_mode": taskgen.get("mode") if taskgen else None,
        "taskgen_object_source_presearch": bool(taskgen.get("object_source_presearch")) if taskgen else False,
        "round_count": len(rounds),
        "alias_round_limit_reached": alias_round_limit_reached,
        "object_seed_count": len(task.get("object_seeds") or []),
        "source_document_count": len(task.get("source_documents") or task.get("documents") or []),
        "candidate_slices": (candidate_payload.get("stats") or {}).get("candidate_slices"),
        "fetch_error_count": len(candidate_payload.get("fetch_errors") or []),
        "fetch_errors": list(candidate_payload.get("fetch_errors") or []),
        "candidate_coverage_gap_count": len(candidate_payload.get("coverage_gaps") or []),
        "objects_without_slices": coverage.get("objects_without_slices") or [],
        "judge_status": judge_payload.get("status") if judge_payload else None,
        "judge_elapsed_seconds": judge_payload.get("_elapsed_seconds") if judge_payload else None,
        "judge_usage": judge_payload.get("_usage") if judge_payload else {},
        "judge_sharded": bool(judge_payload.get("_sharded")) if judge_payload else False,
        "judge_shard_count": int(judge_payload.get("_shard_count") or 0) if judge_payload else 0,
        "claim_count": len(judge_payload.get("claims") or []) if judge_payload else 0,
        "primary_binding_count": len(judge_payload.get("primary_bindings") or judge_payload.get("bindings") or [])
        if judge_payload
        else 0,
        "secondary_binding_count": len(judge_payload.get("secondary_binding_candidates") or [])
        if judge_payload
        else 0,
        "judge_coverage_gap_count": len(judge_payload.get("coverage_gaps") or []) if judge_payload else 0,
        "judge_anomaly_count": len(anomalies),
        "judge_anomaly_block_count": anomaly_totals["block"],
        "judge_anomaly_warning_count": anomaly_totals["warning"],
        "judge_anomalies": anomalies,
        "rounds": list(rounds),
        "files": {
            "final_task": str(person_dir / "task.final.json"),
            "final_candidates": str(person_dir / "candidates.final.json") if final_candidates else None,
            "final_judge_result": str(person_dir / "judge_result.final.json") if final_judge else None,
        },
    }


def build_batch_summary(
    *,
    people: Sequence[Mapping[str, Any]],
    run_root: Path,
    elapsed_seconds: float,
    max_alias_refine_rounds: int,
    candidate_source_refine_rounds: int,
    candidate_source_refine_max_objects: int,
    candidate_source_refine_pages_per_object: int,
    judge_shard_size: int,
    judge_shard_workers: int,
    source_cache_root: Path | None,
    taskgen_streaming: bool,
    taskgen_batch_size: int = 1,
    taskgen_presearch: bool = False,
    taskgen_search_enabled: bool = True,
) -> dict[str, Any]:
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v3_clean_runner.py",
        "run_root": str(run_root),
        "elapsed_seconds": elapsed_seconds,
        "pipeline_elapsed_seconds": elapsed_seconds,
        "targets": [row.get("name") for row in people],
        "people": list(people),
        "totals": {
            "usage": sum_usage(people),
            "candidate_slices": sum(int(row.get("candidate_slices") or 0) for row in people),
            "claim_count": sum(int(row.get("claim_count") or 0) for row in people),
            "fetch_error_count": sum(int(row.get("fetch_error_count") or 0) for row in people),
            "candidate_coverage_gap_count": sum(int(row.get("candidate_coverage_gap_count") or 0) for row in people),
            "judge_coverage_gap_count": sum(int(row.get("judge_coverage_gap_count") or 0) for row in people),
            "judge_anomaly_count": sum(int(row.get("judge_anomaly_count") or 0) for row in people),
            "judge_anomaly_block_count": sum(int(row.get("judge_anomaly_block_count") or 0) for row in people),
            "judge_anomaly_warning_count": sum(int(row.get("judge_anomaly_warning_count") or 0) for row in people),
        },
        "clean_policy": {
            "candidate_alias_missing_auto_patch": True,
            "judge_alias_missing_auto_patch": True,
            "judge_search_enabled": False,
            "codex_ephemeral": True,
            "codex_ignore_user_config": True,
            "codex_ignore_rules": True,
            "old_source_packs_read": False,
            "old_object_pool_read": False,
            "old_judgement_outputs_read": False,
            "taskgen_streaming": taskgen_streaming,
            "taskgen_batch_size": taskgen_batch_size,
            "taskgen_presearch": taskgen_presearch,
            "taskgen_search_enabled": taskgen_search_enabled,
            "max_alias_refine_rounds": max_alias_refine_rounds,
            "candidate_source_refine_rounds": candidate_source_refine_rounds,
            "candidate_source_refine_max_objects": candidate_source_refine_max_objects,
            "candidate_source_refine_pages_per_object": candidate_source_refine_pages_per_object,
            "judge_shard_size": judge_shard_size,
            "judge_shard_workers": judge_shard_workers,
            "source_cache_root": str(source_cache_root) if source_cache_root else None,
        },
    }
