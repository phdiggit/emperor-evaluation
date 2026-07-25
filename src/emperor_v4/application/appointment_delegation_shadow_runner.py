from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.adapters import adapt_claim_extractor_snapshot
from emperor_v4.evaluation.appointment_delegation_scoring import (
    SCORE_CONTRIBUTION_SCHEMA_VERSION,
    PROFILE,
    canonical_hash,
    evaluate_judgment,
    score_judgment,
    validate_scored_demo_manifest,
)
from emperor_v4.evaluation.limited_factor_scoring import LimitedFactorProfile
from emperor_v4.evaluation.factor_evidence_coverage import (
    scope_coverage_to_sources,
)


def run_appointment_delegation_shadow(
    manifest_path: Path | str,
) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    return run_appointment_delegation_shadow_manifest(manifest, path)


def run_appointment_delegation_shadow_manifest(
    manifest: Mapping[str, Any],
    manifest_path: Path | str,
    *,
    prior_report: Mapping[str, Any] | None = None,
    rebuild_unit_refs: set[str] | None = None,
) -> dict[str, Any]:
    return run_limited_factor_shadow_manifest(
        manifest,
        manifest_path,
        profile=PROFILE,
        manifest_validator=validate_scored_demo_manifest,
        judgment_evaluator=evaluate_judgment,
        judgment_scorer=score_judgment,
        prior_report=prior_report,
        rebuild_unit_refs=rebuild_unit_refs,
    )


def run_limited_factor_shadow_manifest(
    manifest: Mapping[str, Any],
    manifest_path: Path | str,
    *,
    profile: LimitedFactorProfile,
    manifest_validator,
    judgment_evaluator,
    judgment_scorer,
    prior_report: Mapping[str, Any] | None = None,
    rebuild_unit_refs: set[str] | None = None,
) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest_validator(manifest)
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
    supplemental_assertion_links: dict[str, str] = {}
    for role, supplemental_path in frozen_paths.items():
        if not role.endswith("claim_snapshot"):
            continue
        supplemental_snapshot = json.loads(
            supplemental_path.read_text(encoding="utf-8")
        )
        for assertion in adapt_claim_extractor_snapshot(supplemental_snapshot):
            if assertion.assertion_code in supplemental_assertion_links:
                raise ValueError(
                    f"补充 Assertion identity 重复: {assertion.assertion_code}"
                )
            supplemental_assertion_links[assertion.assertion_code] = (
                assertion.source_passage_ref
            )
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
            expected_passage_ref = assertions_by_ref[assertion_ref][
                "source_passage_ref"
            ]
            if (
                frozen_links.get(assertion_ref) != expected_passage_ref
                and supplemental_assertion_links.get(assertion_ref)
                != expected_passage_ref
            ):
                raise ValueError(
                    f"Assertion/SourcePassage 未与冻结 snapshot 对齐: {assertion_ref}"
                )

    passages = {row["passage_ref"]: row for row in manifest["source_passages"]}
    assertions = {row["assertion_ref"]: row for row in manifest["assertions"]}
    episodes = {row["episode_ref"]: row for row in manifest["historical_episodes"]}
    sorted_units = sorted(
        manifest["rule_evidence_units"], key=lambda row: row["unit_ref"]
    )
    rebuild_refs = (
        {str(unit["unit_ref"]) for unit in sorted_units}
        if rebuild_unit_refs is None
        else set(rebuild_unit_refs)
    )
    unit_refs = {str(unit["unit_ref"]) for unit in sorted_units}
    if not rebuild_refs <= unit_refs:
        raise ValueError("scored shadow rebuild_unit_refs 包含未知评分单元")
    prior_judgments = {
        str(row["rule_evidence_unit_ref"]): row
        for row in (prior_report or {}).get("judgments") or ()
    }
    prior_contributions = {
        str(row["rule_evidence_unit_ref"]): row
        for row in (prior_report or {}).get("score_contributions") or ()
    }
    reused_refs = unit_refs - rebuild_refs
    if reused_refs and (
        prior_report is None
        or prior_report.get("status") != profile.report_status
        or prior_report.get("versions")
        != {
            "factor_schema_version": profile.factor_schema_version,
            "judgment_policy_version": profile.judgment_policy_version,
            "score_contribution_schema_version": SCORE_CONTRIBUTION_SCHEMA_VERSION,
            "scoring_formula_version": profile.scoring_formula_version,
        }
        or prior_report.get("evidence_coverage") != manifest["evidence_coverage"]
        or not reused_refs <= set(prior_judgments)
    ):
        raise ValueError("scored shadow 缓存缺失、版本不一致或不可精确复用")

    judgments = []
    contributions = []
    for unit in sorted_units:
        unit_ref = str(unit["unit_ref"])
        unit_assertion_refs = {
            assertion_ref
            for episode_ref in unit["episode_refs"]
            for assertion_ref in episodes[episode_ref]["assertion_refs"]
        }
        unit_source_families = [
            passages[assertions[ref]["source_passage_ref"]]["source_title"]
            for ref in unit_assertion_refs
        ]
        covered_unit = {
            **unit,
            "evidence_coverage": scope_coverage_to_sources(
                manifest["evidence_coverage"], unit_source_families
            ),
        }
        judgment = (
            judgment_evaluator(covered_unit, episodes, assertions)
            if unit_ref in rebuild_refs
            else dict(prior_judgments[unit_ref])
        )
        judgments.append(judgment)
        contribution = (
            judgment_scorer(judgment)
            if unit_ref in rebuild_refs
            else prior_contributions.get(unit_ref)
        )
        if contribution is not None:
            contributions.append(dict(contribution))

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
                    sorted(
                        Counter(
                            row["direction"] or row["applicability"]
                            for row in ruler_judgments
                        ).items()
                    )
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
        "status": profile.report_status,
        "task_code": manifest["task_code"],
        "result_scope": "shadow_demo_only",
        "input_manifest_ref": manifest["manifest_code"],
        "input_manifest_sha256": canonical_hash(manifest),
        "evidence_coverage": dict(manifest["evidence_coverage"]),
        "frozen_input_audit": frozen_input_audit,
        "versions": {
            "factor_schema_version": profile.factor_schema_version,
            "judgment_policy_version": profile.judgment_policy_version,
            "score_contribution_schema_version": SCORE_CONTRIBUTION_SCHEMA_VERSION,
            "scoring_formula_version": profile.scoring_formula_version,
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
            "judgment_cache_hit_count": len(reused_refs),
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
