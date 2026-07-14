from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import json
import yaml

from emperor_v4.application.appointment_delegation_shadow_runner import (
    run_appointment_delegation_shadow,
)
from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash
from emperor_v4.evaluation.appointment_delegation_v3_parity import (
    FACTOR_SCHEMA_VERSION,
    JUDGMENT_POLICY_VERSION,
    SCORING_FORMULA_VERSION,
    aggregate_rulers,
    build_score_contribution,
    evaluate_factor_proposal,
    validate_parity_manifest,
)


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected YAML object")
    return payload


def _resolve_source_path(manifest_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    relative = (manifest_path.parent / candidate).resolve()
    if relative.exists():
        return relative
    raise ValueError(f"V3 parity source manifest 不存在: {raw_path}")


def run_appointment_delegation_v3_parity_shadow(
    manifest_path: Path,
    prior_report_path: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _read_yaml(manifest_path)
    source_path = _resolve_source_path(
        manifest_path, str(manifest.get("source_scored_manifest_path") or "")
    )
    source_manifest = _read_yaml(source_path)
    validate_parity_manifest(manifest, source_manifest)

    baseline = run_appointment_delegation_shadow(source_path)
    if (
        baseline.get("status") != "appointment_delegation_scored_shadow_ready"
        or baseline.get("side_effect_audit", {}).get("model_call_count") != 0
        or baseline.get("side_effect_audit", {}).get("database_write_count") != 0
    ):
        raise ValueError("V3 parity baseline scored shadow 非法或产生副作用")

    unit_by_ref = {
        str(row["unit_ref"]): row
        for row in source_manifest["rule_evidence_units"]
    }
    proposal_by_ref = {
        str(row["unit_ref"]): row
        for row in manifest["factor_judgment_proposals"]
    }
    baseline_judgment_by_unit = {
        str(row["rule_evidence_unit_ref"]): row for row in baseline["judgments"]
    }
    desired_judgments = [
        evaluate_factor_proposal(
            proposal_by_ref[unit_ref],
            unit_by_ref[unit_ref],
            baseline_judgment_by_unit[unit_ref]["input_semantic_fingerprint"],
        )
        for unit_ref in sorted(unit_by_ref)
    ]
    prior_report: Mapping[str, Any] = {}
    if prior_report_path is not None:
        prior_report = json.loads(
            prior_report_path.resolve().read_text(encoding="utf-8")
        )
        if (
            prior_report.get("status")
            != "appointment_delegation_v3_parity_shadow_ready"
            or prior_report.get("versions", {}).get("factor_schema_version")
            != FACTOR_SCHEMA_VERSION
            or prior_report.get("versions", {}).get("judgment_policy_version")
            != JUDGMENT_POLICY_VERSION
            or prior_report.get("versions", {}).get("scoring_formula_version")
            != SCORING_FORMULA_VERSION
        ):
            raise ValueError("V3 parity prior report 版本或状态非法")
    prior_judgments = {
        str(row["rule_evidence_unit_ref"]): row
        for row in prior_report.get("judgments") or ()
    }
    judgments = []
    reused_judgment_refs: list[str] = []
    rebuilt_judgment_refs: list[str] = []
    for desired in desired_judgments:
        unit_ref = str(desired["rule_evidence_unit_ref"])
        prior = prior_judgments.get(unit_ref)
        if prior and prior.get("semantic_fingerprint") == desired["semantic_fingerprint"]:
            judgments.append(dict(prior))
            reused_judgment_refs.append(unit_ref)
        else:
            judgments.append(desired)
            rebuilt_judgment_refs.append(unit_ref)

    desired_contributions = [build_score_contribution(row) for row in judgments]
    prior_contributions = {
        str(row["rule_evidence_unit_ref"]): row
        for row in prior_report.get("score_contributions") or ()
    }
    contributions = []
    reused_contribution_refs: list[str] = []
    rebuilt_contribution_refs: list[str] = []
    for desired in desired_contributions:
        unit_ref = str(desired["rule_evidence_unit_ref"])
        prior = prior_contributions.get(unit_ref)
        if prior and prior.get("semantic_fingerprint") == desired["semantic_fingerprint"]:
            contributions.append(dict(prior))
            reused_contribution_refs.append(unit_ref)
        else:
            contributions.append(desired)
            rebuilt_contribution_refs.append(unit_ref)
    rulers = sorted({row["ruler"] for row in judgments})
    aggregates = aggregate_rulers(contributions, rulers)

    baseline_by_unit = {
        str(row["rule_evidence_unit_ref"]): row
        for row in baseline["score_contributions"]
    }
    comparison = [
        {
            "rule_evidence_unit_ref": row["rule_evidence_unit_ref"],
            "ruler": row["ruler"],
            "person": row["person"],
            "limited_factor_v1_normalized_contribution": baseline_by_unit[
                row["rule_evidence_unit_ref"]
            ]["normalized_contribution"],
            "v3_parity_material_count": len(row["factor_materials"]),
            "v3_parity_raw_net_before_density": row["raw_net_before_density"],
            "same_direction_only_is_no_longer_same_score": True,
        }
        for row in contributions
    ]
    baseline_distinct = len(
        {
            row["limited_factor_v1_normalized_contribution"]
            for row in comparison
        }
    )
    parity_distinct = len(
        {row["v3_parity_raw_net_before_density"] for row in comparison}
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "appointment_delegation_v3_parity_shadow_ready",
        "task_code": manifest["task_code"],
        "manifest_code": manifest["manifest_code"],
        "source_scored_manifest": manifest["source_scored_manifest_path"],
        "versions": {
            "factor_schema_version": FACTOR_SCHEMA_VERSION,
            "judgment_policy_version": JUDGMENT_POLICY_VERSION,
            "scoring_formula_version": SCORING_FORMULA_VERSION,
        },
        "summary": {
            "ruler_count": len(rulers),
            "rule_evidence_unit_count": len(judgments),
            "judgment_proposal_count": len(judgments),
            "score_contribution_count": len(contributions),
            "factor_material_count": sum(
                len(row["factor_materials"]) for row in judgments
            ),
            "mixed_unit_count": sum(
                {material["side"] for material in row["factor_materials"]}
                == {"positive", "negative"}
                for row in judgments
            ),
            "baseline_distinct_unit_score_count": baseline_distinct,
            "v3_parity_distinct_unit_score_count": parity_distinct,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_score_write_count": 0,
            "rebuilt_judgment_count": len(rebuilt_judgment_refs),
            "reused_judgment_count": len(reused_judgment_refs),
            "rebuilt_score_contribution_count": len(rebuilt_contribution_refs),
            "reused_score_contribution_count": len(reused_contribution_refs),
        },
        "judgments": judgments,
        "score_contributions": contributions,
        "ruler_aggregates": aggregates,
        "baseline_comparison": comparison,
        "incremental_reuse": {
            "rebuilt_judgment_unit_refs": rebuilt_judgment_refs,
            "reused_judgment_unit_refs": reused_judgment_refs,
            "rebuilt_score_contribution_unit_refs": rebuilt_contribution_refs,
            "reused_score_contribution_unit_refs": reused_contribution_refs,
            "unexpected_invalidation_count": 0,
        },
        "migration_contract": {
            "reused_v4_artifacts": [
                "SourcePassage",
                "Assertion",
                "HistoricalEpisode",
                "RuleEvidenceUnit",
                "prior_v4_factor_observations",
            ],
            "invalidated_from": "Judgment",
            "agent_output_may_choose_option_codes_only": True,
            "agent_output_may_supply_numeric_values": False,
            "deterministic_formula_only": True,
            "human_review_required_for_shadow_proposals": True,
            "formal_acceptance_performed": False,
        },
        "side_effect_audit": {
            "offline": True,
            "report_only": True,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
            "formal_scoring_performed": False,
        },
    }
    report["report_sha256"] = canonical_hash(report)
    return report
