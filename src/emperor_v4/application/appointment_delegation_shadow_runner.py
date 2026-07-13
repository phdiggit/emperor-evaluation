from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.evaluation.appointment_delegation_scoring import (
    FACTOR_SCHEMA_VERSION,
    JUDGMENT_POLICY_VERSION,
    SCORE_CONTRIBUTION_SCHEMA_VERSION,
    SCORING_FORMULA_VERSION,
    canonical_hash,
    evaluate_judgment,
    score_judgment,
    validate_scored_demo_manifest,
)


def run_appointment_delegation_shadow(
    manifest_path: Path | str,
) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_scored_demo_manifest(manifest)
    repo_root = path.resolve().parents[2]
    frozen_input_audit = []
    frozen_paths: dict[str, Path] = {}
    for frozen_input in manifest.get("frozen_basis", {}).get("inputs", []):
        input_path = repo_root / frozen_input["path"]
        if not input_path.is_file():
            raise ValueError(f"冻结输入不存在: {frozen_input['path']}")
        actual = hashlib.sha256(input_path.read_bytes()).hexdigest()
        if actual != frozen_input["sha256"]:
            raise ValueError(f"冻结输入 hash 已变化: {frozen_input['path']}")
        frozen_input_audit.append(
            {
                "path": frozen_input["path"],
                "role": frozen_input["role"],
                "sha256": actual,
                "verified": True,
            }
        )
        frozen_paths[frozen_input["role"]] = input_path

    episode_snapshot_path = frozen_paths.get("episode_snapshot")
    if episode_snapshot_path is None:
        raise ValueError("冻结输入缺少 episode_snapshot")
    snapshot = json.loads(episode_snapshot_path.read_text(encoding="utf-8"))
    frozen_packets = {row["episode_code"]: row for row in snapshot["packets"]}
    assertions_by_ref = {
        row["assertion_ref"]: row for row in manifest["assertions"]
    }
    for episode in manifest["historical_episodes"]:
        frozen = frozen_packets.get(episode["episode_code"])
        if (
            frozen is None
            or frozen["semantic_fingerprint"] != episode["semantic_fingerprint"]
        ):
            raise ValueError(f"Episode 未与冻结 snapshot 对齐: {episode['episode_code']}")
        frozen_links = {
            row["assertion_ref"]: row["source_passage_ref"]
            for row in frozen["assertion_links"]
        }
        for assertion_ref in episode["assertion_refs"]:
            if frozen_links.get(assertion_ref) != assertions_by_ref[assertion_ref][
                "source_passage_ref"
            ]:
                raise ValueError(
                    f"Assertion/SourcePassage 未与冻结 snapshot 对齐: {assertion_ref}"
                )

    passages = {row["passage_ref"]: row for row in manifest["source_passages"]}
    assertions = {row["assertion_ref"]: row for row in manifest["assertions"]}
    episodes = {row["episode_ref"]: row for row in manifest["historical_episodes"]}
    judgments = [
        evaluate_judgment(unit, episodes, assertions)
        for unit in sorted(manifest["rule_evidence_units"], key=lambda row: row["unit_ref"])
    ]
    contributions = [
        contribution
        for judgment in judgments
        if (contribution := score_judgment(judgment)) is not None
    ]

    rulers = sorted({judgment["ruler"] for judgment in judgments})
    aggregates = []
    for ruler in rulers:
        ruler_judgments = [row for row in judgments if row["ruler"] == ruler]
        ruler_contributions = [row for row in contributions if row["ruler"] == ruler]
        total = round(
            sum(row["normalized_contribution"] for row in ruler_contributions), 4
        )
        aggregates.append(
            {
                "ruler": ruler,
                "unit_count": len(ruler_judgments),
                "scored_unit_count": len(ruler_contributions),
                "blocked_unit_count": sum(bool(row["blockers"]) for row in ruler_judgments),
                "direction_counts": dict(
                    sorted(Counter(row["direction"] for row in ruler_judgments).items())
                ),
                "shadow_contribution_sum": total,
                "shadow_contribution_mean": (
                    round(total / len(ruler_contributions), 4)
                    if ruler_contributions
                    else None
                ),
                "not_a_formal_45_point_score": True,
            }
        )

    used_assertions = sorted(
        {ref for judgment in judgments for ref in judgment["supporting_assertion_refs"]}
    )
    used_passages = sorted(
        {assertions[ref]["source_passage_ref"] for ref in used_assertions}
    )
    consumed_episodes = [
        ref for judgment in judgments for ref in judgment["episode_refs"]
    ]
    duplicate_episodes = sorted(
        ref for ref in set(consumed_episodes) if consumed_episodes.count(ref) > 1
    )
    contribution_by_unit = {
        row["rule_evidence_unit_ref"]: row for row in contributions
    }
    scored_units = []
    for judgment in judgments:
        contribution = contribution_by_unit.get(judgment["rule_evidence_unit_ref"])
        scored_units.append(
            {
                "ruler": judgment["ruler"],
                "person": judgment["person"],
                "rule_evidence_unit_ref": judgment["rule_evidence_unit_ref"],
                "factor_values": judgment["factor_values"],
                "direction": judgment["direction"],
                "normalized_contribution": (
                    contribution["normalized_contribution"] if contribution else None
                ),
                "confidence": judgment["confidence"],
                "blockers": judgment["blockers"],
                "lineage": (
                    contribution["lineage"]
                    if contribution
                    else {
                        "episode_refs": judgment["episode_refs"],
                        "assertion_refs": judgment["supporting_assertion_refs"],
                        "source_passage_refs": judgment[
                            "supporting_source_passage_refs"
                        ],
                    }
                ),
            }
        )
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "appointment_delegation_scored_shadow_ready",
        "task_code": manifest["task_code"],
        "result_scope": "shadow_demo_only",
        "input_manifest_ref": manifest["manifest_code"],
        "input_manifest_sha256": canonical_hash(manifest),
        "frozen_input_audit": frozen_input_audit,
        "versions": {
            "factor_schema_version": FACTOR_SCHEMA_VERSION,
            "judgment_policy_version": JUDGMENT_POLICY_VERSION,
            "score_contribution_schema_version": SCORE_CONTRIBUTION_SCHEMA_VERSION,
            "scoring_formula_version": SCORING_FORMULA_VERSION,
        },
        "summary": {
            "ruler_count": len(rulers),
            "rule_evidence_unit_count": len(judgments),
            "judgment_count": len(judgments),
            "score_contribution_count": len(contributions),
            "blocked_unit_count": sum(bool(row["blockers"]) for row in judgments),
            "duplicate_consumption_episode_refs": duplicate_episodes,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "source_cache_hit_count": len(used_passages),
            "judgment_cache_hit_count": 0,
        },
        "judgments": judgments,
        "score_contributions": contributions,
        "scored_units": scored_units,
        "ruler_aggregates": aggregates,
        "lineage": {
            "source_passages": [passages[ref] for ref in used_passages],
            "assertions": [assertions[ref] for ref in used_assertions],
            "historical_episodes": [episodes[ref] for ref in sorted(set(consumed_episodes))],
        },
        "side_effect_audit": {
            "offline": True,
            "report_only": True,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
    }
    report["report_sha256"] = canonical_hash(report)
    return report
